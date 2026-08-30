"""
CryptoSignalPro AI - Trade Günlüğü & Trade Notları ve Fiyat Alarmı Servisi (v2.1.0)

Gelişmiş Yetenekler:
1. Depozito & Kasa / Bakiye Takibi:
   - Başlangıç depozitosu (Initial Capital / Deposit) yönetimi.
   - Kasa büyümesi (Account Growth %), Güncel Bakiye (Current Balance) ve marjin kullanımı (% Kasa Riski).
2. Kaldıraç & Marjin Sistemi (Leverage & Margin):
   - Spot (1x) veya Vadeli (2x - 100x) kaldıraç desteği.
   - Kullanılan marjin ($) ve Toplam pozisyon büyüklüğü ($ = Marjin x Kaldıraç).
3. 💸 Otomatik & Manuel Komisyon (Trading Fee) Kesintisi:
   - Pozisyon büyüklüğüne göre otomatik giriş + çıkış komisyonu (Örn: %0.05 Taker/Maker).
   - Brüt Kâr/Zarar (Gross PnL) - Komisyon = Net Kâr/Zarar (Net PnL).
   - Net ROE % ve Kasa bakiyesinden komisyonların eksiksiz düşülmesi.
4. Takvim Bazlı Günlük Özeti (Daily Trading Calendar Aggregation):
   - Gün bazlı net kazançlar, komisyonlar ve günlük karne.
5. Trade Notları & 7/24 Fiyat Alarm Motoru.
"""

import os
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import numpy as np

from engine.market_data import market_manager


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
JOURNAL_FILE = os.path.join(DATA_DIR, "trade_journal.json")
NOTES_FILE = os.path.join(DATA_DIR, "trade_notes.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "journal_settings.json")


def load_journal_settings() -> Dict[str, Any]:
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"initial_deposit": 1000.0, "default_fee_pct": 0.05, "currency": "USDT"}


def save_journal_settings(settings: Dict[str, Any]):
    try:
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Journal settings kaydetme hatası: {e}")


class TradeJournalManager:
    def __init__(self):
        self.trades: List[Dict[str, Any]] = self._load_journal()
        self.settings: Dict[str, Any] = load_journal_settings()

    def _load_journal(self) -> List[Dict[str, Any]]:
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR, exist_ok=True)
        if os.path.exists(JOURNAL_FILE):
            try:
                with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Trade Journal okuma hatası: {e}")
        return []

    def _save_journal(self):
        try:
            if not os.path.exists(DATA_DIR):
                os.makedirs(DATA_DIR, exist_ok=True)
            with open(JOURNAL_FILE, "w", encoding="utf-8") as f:
                json.dump(self.trades, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Trade Journal kaydetme hatası: {e}")

    def update_initial_deposit(self, deposit_amount: float, default_fee_pct: Optional[float] = None) -> Dict[str, Any]:
        self.settings["initial_deposit"] = max(1.0, float(deposit_amount))
        if default_fee_pct is not None:
            self.settings["default_fee_pct"] = max(0.0, float(default_fee_pct))
        save_journal_settings(self.settings)
        return self.settings

    def get_all_trades(self, status: Optional[str] = None, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        result = self.trades
        if status and status != "ALL":
            result = [t for t in result if t.get("status") == status]
        if symbol:
            sym_clean = symbol.upper().strip()
            result = [t for t in result if sym_clean in t.get("symbol", "")]
        # En yeni işlem en üstte
        return sorted(result, key=lambda x: x.get("created_at", 0), reverse=True)

    def add_trade(self, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        trade_id = trade_data.get("id") or str(uuid.uuid4())[:8]
        now = time.time()
        
        entry_price = float(trade_data.get("entry_price", 0.0))
        target_price = float(trade_data.get("target_price", 0.0))
        stop_loss = float(trade_data.get("stop_loss", 0.0))
        direction = trade_data.get("direction", "LONG").upper()
        
        # Kaldıraç (1x = Spot, 2x - 100x = Vadeli)
        leverage = max(1, int(trade_data.get("leverage") or 1))
        
        # Marjin ($) ve Toplam Pozisyon Büyüklüğü ($)
        margin = float(trade_data.get("margin") or 0.0)
        position_size = float(trade_data.get("position_size") or 0.0)

        if margin <= 0 and position_size > 0:
            margin = round(position_size / leverage, 2)
        elif margin > 0 and position_size <= 0:
            position_size = round(margin * leverage, 2)
        elif margin <= 0 and position_size <= 0:
            margin = 100.0
            position_size = margin * leverage

        init_deposit = self.settings.get("initial_deposit", 1000.0)
        deposit_pct_used = round((margin / init_deposit) * 100.0, 1) if init_deposit > 0 else 0.0

        # 💸 Komisyon Hesabı (Giriş + Çıkış Toplamı)
        # Kullanıcı elle girdiyse onu al, girmediyse (Pozisyon * Komisyon Oranı * 2) hesapla
        default_fee_rate = float(self.settings.get("default_fee_pct", 0.05))
        fee_rate_pct = float(trade_data.get("fee_rate_pct") or default_fee_rate)
        
        if trade_data.get("fee") is not None and str(trade_data.get("fee")).strip() != "":
            fee = float(trade_data.get("fee"))
        else:
            fee = round(position_size * (fee_rate_pct / 100.0) * 2, 2)

        # Otomatik Risk / Ödül Oranı
        risk_dist = abs(entry_price - stop_loss) if entry_price and stop_loss else 0.0
        reward_dist = abs(target_price - entry_price) if target_price and entry_price else 0.0
        rr_ratio = round(reward_dist / risk_dist, 2) if risk_dist > 0 else 0.0

        status = trade_data.get("status", "OPEN").upper()
        exit_price = float(trade_data.get("exit_price")) if trade_data.get("exit_price") else None
        
        pnl_percent_raw = 0.0  # Ham fiyat değişimi %
        pnl_percent_roe = 0.0  # Kaldıraçlı marjin getirisi %
        gross_pnl_amount = 0.0 # Brüt kâr/zarar ($)
        net_pnl_amount = 0.0   # Komisyon düşülmüş Net kâr/zarar ($)

        if exit_price and exit_price > 0 and entry_price > 0:
            if direction == "LONG":
                pnl_percent_raw = round((exit_price - entry_price) / entry_price * 100.0, 2)
            else:
                pnl_percent_raw = round((entry_price - exit_price) / entry_price * 100.0, 2)
            
            pnl_percent_roe = round(pnl_percent_raw * leverage, 2)
            gross_pnl_amount = round(margin * (pnl_percent_roe / 100.0), 2)
            net_pnl_amount = round(gross_pnl_amount - fee, 2)
            
            # Net ROE %
            if margin > 0:
                net_pnl_percent_roe = round((net_pnl_amount / margin) * 100.0, 2)
            else:
                net_pnl_percent_roe = pnl_percent_roe
        else:
            net_pnl_percent_roe = 0.0

        entry_date_str = trade_data.get("entry_date_str") or datetime.now().strftime("%Y-%m-%d %H:%M")
        if trade_data.get("entry_date_str"):
            try:
                clean_ds = str(trade_data["entry_date_str"]).replace("T", " ").strip()
                dt = datetime.strptime(clean_ds[:16], "%Y-%m-%d %H:%M")
                now = dt.timestamp()
                entry_date_str = clean_ds[:16]
            except Exception:
                pass

        new_trade = {
            "id": trade_id,
            "symbol": trade_data.get("symbol", "BTC/USDT").upper().strip(),
            "direction": direction,
            "leverage": leverage,
            "margin": margin,
            "position_size": position_size,
            "deposit_pct_used": deposit_pct_used,
            "fee": fee,
            "fee_rate_pct": fee_rate_pct,
            "entry_price": entry_price,
            "target_price": target_price,
            "stop_loss": stop_loss,
            "exit_price": exit_price,
            "status": status, # OPEN, WIN_TP, LOSS_SL, CLOSED, CANCELLED
            "risk_reward": rr_ratio,
            "gross_pnl_amount": gross_pnl_amount,
            "pnl_amount": net_pnl_amount,     # Net Kâr/Zarar ($) (Komisyon düşülmüş)
            "pnl_percent": net_pnl_percent_roe, # Net ROE % (Komisyon düşülmüş)
            "pnl_percent_raw": pnl_percent_raw,
            "strategy": trade_data.get("strategy", "Kişisel Analiz"),
            "notes": trade_data.get("notes", ""),
            "entry_date_str": entry_date_str,
            "exit_date_str": trade_data.get("exit_date_str"),
            "created_at": now,
            "updated_at": time.time()
        }

        self.trades.append(new_trade)
        self._save_journal()
        return new_trade

    def update_trade(self, trade_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for trade in self.trades:
            if trade.get("id") == trade_id:
                for k, v in updates.items():
                    if k != "id":
                        trade[k] = v

                if updates.get("entry_date_str"):
                    try:
                        clean_ds = str(updates["entry_date_str"]).replace("T", " ").strip()
                        dt = datetime.strptime(clean_ds[:16], "%Y-%m-%d %H:%M")
                        trade["created_at"] = dt.timestamp()
                        trade["entry_date_str"] = clean_ds[:16]
                    except Exception:
                        pass

                # Kaldıraç & Marjin güncelleme
                leverage = max(1, int(trade.get("leverage") or 1))
                margin = float(trade.get("margin") or 0.0)
                position_size = float(trade.get("position_size") or 0.0)

                if margin <= 0 and position_size > 0:
                    margin = round(position_size / leverage, 2)
                    trade["margin"] = margin
                elif margin > 0 and (position_size <= 0 or "margin" in updates or "leverage" in updates):
                    position_size = round(margin * leverage, 2)
                    trade["position_size"] = position_size

                init_deposit = self.settings.get("initial_deposit", 1000.0)
                trade["deposit_pct_used"] = round((margin / init_deposit) * 100.0, 1) if init_deposit > 0 else 0.0

                # 💸 Komisyon Güncelleme
                if "fee" in updates and updates["fee"] is not None and str(updates["fee"]).strip() != "":
                    fee = float(updates["fee"])
                else:
                    fee_rate = float(trade.get("fee_rate_pct") or self.settings.get("default_fee_pct", 0.05))
                    fee = round(position_size * (fee_rate / 100.0) * 2, 2)
                trade["fee"] = fee

                # PnL'i güncelle
                entry_price = float(trade.get("entry_price", 0.0))
                exit_price = float(trade.get("exit_price", 0.0)) if trade.get("exit_price") else None
                direction = trade.get("direction", "LONG")

                if exit_price and exit_price > 0 and entry_price > 0:
                    if direction == "LONG":
                        pnl_raw = round((exit_price - entry_price) / entry_price * 100.0, 2)
                    else:
                        pnl_raw = round((entry_price - exit_price) / entry_price * 100.0, 2)
                    
                    pnl_roe = round(pnl_raw * leverage, 2)
                    gross_pnl = round(margin * (pnl_roe / 100.0), 2)
                    net_pnl = round(gross_pnl - fee, 2)
                    
                    trade["pnl_percent_raw"] = pnl_raw
                    trade["gross_pnl_amount"] = gross_pnl
                    trade["pnl_amount"] = net_pnl
                    trade["pnl_percent"] = round((net_pnl / margin) * 100.0, 2) if margin > 0 else pnl_roe
                
                trade["updated_at"] = time.time()
                self._save_journal()
                return trade
        return None

    def delete_trade(self, trade_id: str) -> bool:
        initial_len = len(self.trades)
        self.trades = [t for t in self.trades if t.get("id") != trade_id]
        if len(self.trades) < initial_len:
            self._save_journal()
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Tüm işlemlerin, komisyonların ve takvim bazlı performans karnesini hesaplar."""
        total_trades = len(self.trades)
        initial_deposit = float(self.settings.get("initial_deposit", 1000.0))
        default_fee_pct = float(self.settings.get("default_fee_pct", 0.05))

        if total_trades == 0:
            return {
                "initial_deposit": initial_deposit,
                "current_balance": initial_deposit,
                "account_growth_pct": 0.0,
                "default_fee_pct": default_fee_pct,
                "total_trades": 0,
                "open_trades": 0,
                "closed_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_fees_paid": 0.0,
                "gross_pnl_amount": 0.0,
                "total_pnl_pct": 0.0,
                "total_pnl_amount": 0.0,
                "avg_rr": 0.0,
                "avg_leverage": 1.0,
                "profit_factor": 0.0,
                "best_trade_pnl": 0.0,
                "worst_trade_pnl": 0.0,
                "daily_calendar": {}
            }

        open_trades = [t for t in self.trades if t.get("status") == "OPEN"]
        closed_trades = [t for t in self.trades if t.get("status") in ["WIN_TP", "LOSS_SL", "CLOSED"]]

        wins = [t for t in closed_trades if t.get("pnl_amount", 0.0) > 0 or t.get("status") == "WIN_TP"]
        losses = [t for t in closed_trades if t.get("pnl_amount", 0.0) < 0 or t.get("status") == "LOSS_SL"]

        win_rate = round(len(wins) / len(closed_trades) * 100.0, 1) if closed_trades else 0.0
        total_fees_paid = round(sum(t.get("fee", 0.0) for t in closed_trades), 2)
        gross_pnl_amount = round(sum(t.get("gross_pnl_amount", t.get("pnl_amount", 0.0)) for t in closed_trades), 2)
        total_pnl_amount = round(sum(t.get("pnl_amount", 0.0) for t in closed_trades), 2)
        total_pnl_pct = round(sum(t.get("pnl_percent", 0.0) for t in closed_trades), 2)
        
        avg_rr = round(sum(t.get("risk_reward", 0.0) for t in self.trades) / total_trades, 2)
        avg_leverage = round(sum(t.get("leverage", 1) for t in self.trades) / total_trades, 1)

        # Net bakiye = Başlangıç Depozitosu + Net PnL (Komisyonlar otomatik düşülmüş)
        current_balance = round(initial_deposit + total_pnl_amount, 2)
        account_growth_pct = round((total_pnl_amount / initial_deposit) * 100.0, 2) if initial_deposit > 0 else 0.0

        gross_profit = sum(t.get("pnl_amount", 0.0) for t in wins if t.get("pnl_amount", 0.0) > 0)
        gross_loss = abs(sum(t.get("pnl_amount", 0.0) for t in losses if t.get("pnl_amount", 0.0) < 0))
        
        if gross_loss > 0:
            profit_factor = round(gross_profit / gross_loss, 2)
        else:
            profit_factor = round(gross_profit, 2) if gross_profit > 0 else (1.0 if wins else 0.0)

        pnl_amounts = [t.get("pnl_amount", 0.0) for t in closed_trades]
        best_trade_pnl = max(pnl_amounts) if pnl_amounts else 0.0
        worst_trade_pnl = min(pnl_amounts) if pnl_amounts else 0.0

        # -------------------------------------------------------------
        # 📅 TAKVİM BAZLI GÜNLÜK ÖZET HARİTASI (DAILY CALENDAR MAP)
        # -------------------------------------------------------------
        daily_calendar: Dict[str, Dict[str, Any]] = {}
        for t in self.trades:
            dt_str = t.get("entry_date_str") or ""
            day_key = dt_str[:10] if len(dt_str) >= 10 else datetime.fromtimestamp(t.get("created_at", time.time())).strftime("%Y-%m-%d")

            if day_key not in daily_calendar:
                daily_calendar[day_key] = {
                    "date": day_key,
                    "trade_count": 0,
                    "win_count": 0,
                    "loss_count": 0,
                    "open_count": 0,
                    "net_pnl_amount": 0.0,
                    "net_pnl_pct": 0.0,
                    "total_fee": 0.0,
                    "trades": []
                }

            day_obj = daily_calendar[day_key]
            day_obj["trade_count"] += 1
            
            pnl_amt = float(t.get("pnl_amount", 0.0))
            pnl_pct = float(t.get("pnl_percent", 0.0))
            fee_amt = float(t.get("fee", 0.0))
            status = t.get("status", "OPEN")

            if status == "OPEN":
                day_obj["open_count"] += 1
            else:
                day_obj["total_fee"] = round(day_obj["total_fee"] + fee_amt, 2)
                day_obj["net_pnl_amount"] = round(day_obj["net_pnl_amount"] + pnl_amt, 2)
                day_obj["net_pnl_pct"] = round(day_obj["net_pnl_pct"] + pnl_pct, 2)

                if pnl_amt > 0 or status == "WIN_TP":
                    day_obj["win_count"] += 1
                elif pnl_amt < 0 or status == "LOSS_SL":
                    day_obj["loss_count"] += 1

            day_obj["trades"].append({
                "id": t.get("id"),
                "symbol": t.get("symbol"),
                "direction": t.get("direction"),
                "leverage": t.get("leverage", 1),
                "margin": t.get("margin", 0.0),
                "position_size": t.get("position_size", 0.0),
                "fee": fee_amt,
                "gross_pnl_amount": t.get("gross_pnl_amount", pnl_amt),
                "pnl_amount": pnl_amt,
                "pnl_percent": pnl_pct,
                "status": status,
                "strategy": t.get("strategy"),
                "entry_date_str": t.get("entry_date_str")
            })

        return {
            "initial_deposit": initial_deposit,
            "current_balance": current_balance,
            "account_growth_pct": account_growth_pct,
            "default_fee_pct": default_fee_pct,
            "total_trades": total_trades,
            "open_trades": len(open_trades),
            "closed_trades": len(closed_trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": win_rate,
            "total_fees_paid": total_fees_paid,
            "gross_pnl_amount": gross_pnl_amount,
            "total_pnl_pct": total_pnl_pct,
            "total_pnl_amount": total_pnl_amount,
            "avg_rr": avg_rr,
            "avg_leverage": avg_leverage,
            "profit_factor": profit_factor,
            "best_trade_pnl": best_trade_pnl,
            "worst_trade_pnl": worst_trade_pnl,
            "daily_calendar": daily_calendar
        }


class TradeNotesAlertManager:
    def __init__(self):
        self.notes: List[Dict[str, Any]] = self._load_notes()

    def _load_notes(self) -> List[Dict[str, Any]]:
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR, exist_ok=True)
        if os.path.exists(NOTES_FILE):
            try:
                with open(NOTES_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Trade Notes okuma hatası: {e}")
        return []

    def _save_notes(self):
        try:
            if not os.path.exists(DATA_DIR):
                os.makedirs(DATA_DIR, exist_ok=True)
            with open(NOTES_FILE, "w", encoding="utf-8") as f:
                json.dump(self.notes, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Trade Notes kaydetme hatası: {e}")

    def get_all_notes(self) -> List[Dict[str, Any]]:
        return sorted(self.notes, key=lambda x: x.get("created_at", 0), reverse=True)

    def add_note(self, note_data: Dict[str, Any]) -> Dict[str, Any]:
        note_id = note_data.get("id") or str(uuid.uuid4())[:8]
        now = time.time()
        symbol = note_data.get("symbol", "BTC/USDT").upper().strip()
        if not symbol.endswith("/USDT") and not symbol.endswith("USDT"):
            symbol = f"{symbol}/USDT"

        target_price = float(note_data.get("target_price", 0.0))
        created_price = float(note_data.get("created_price", 0.0))

        if created_price <= 0:
            try:
                df = market_manager.get_market_data(symbol, timeframe="1h", limit=5)
                if df is not None and len(df) > 0:
                    created_price = float(df['close'].iloc[-1])
            except Exception:
                created_price = target_price

        condition_type = note_data.get("condition_type")
        if not condition_type:
            if target_price > created_price:
                condition_type = "CROSS_ABOVE"
            else:
                condition_type = "CROSS_BELOW"

        created_at_str = note_data.get("created_at_str")
        if created_at_str:
            try:
                clean_ds = str(created_at_str).replace("T", " ").strip()
                dt = datetime.strptime(clean_ds[:16], "%Y-%m-%d %H:%M")
                now = dt.timestamp()
                created_at_str = clean_ds[:16]
            except Exception:
                created_at_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        else:
            created_at_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        new_note = {
            "id": note_id,
            "symbol": symbol,
            "target_price": target_price,
            "created_price": created_price,
            "condition_type": condition_type,
            "direction_bias": note_data.get("direction_bias", "NÖTR").upper(),
            "note_title": note_data.get("note_title", "Özel Hedef Takibi"),
            "note_text": note_data.get("note_text", ""),
            "telegram_notify": bool(note_data.get("telegram_notify", True)),
            "is_active": True,
            "is_triggered": False,
            "triggered_at": None,
            "triggered_price": None,
            "created_at": now,
            "created_at_str": created_at_str
        }

        self.notes.append(new_note)
        self._save_notes()
        return new_note

    def update_note(self, note_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for note in self.notes:
            if note.get("id") == note_id:
                for k, v in updates.items():
                    if k != "id":
                        note[k] = v
                self._save_notes()
                return note
        return None

    def toggle_note_active(self, note_id: str) -> Optional[Dict[str, Any]]:
        for note in self.notes:
            if note.get("id") == note_id:
                note["is_active"] = not note.get("is_active", True)
                if note["is_active"]:
                    note["is_triggered"] = False
                    note["triggered_at"] = None
                    note["triggered_price"] = None
                self._save_notes()
                return note
        return None

    def delete_note(self, note_id: str) -> bool:
        initial_len = len(self.notes)
        self.notes = [n for n in self.notes if n.get("id") != note_id]
        if len(self.notes) < initial_len:
            self._save_notes()
            return True
        return False

    def check_and_trigger_alerts(self) -> List[Dict[str, Any]]:
        active_notes = [n for n in self.notes if n.get("is_active", True) and not n.get("is_triggered", False)]
        if not active_notes:
            return []

        triggered_list = []
        symbols = list(set(n["symbol"] for n in active_notes))

        price_map = {}
        for sym in symbols:
            try:
                df = market_manager.get_market_data(sym, timeframe="15m", limit=5)
                if df is not None and len(df) > 0:
                    price_map[sym] = float(df['close'].iloc[-1])
            except Exception:
                pass

        for note in active_notes:
            sym = note["symbol"]
            curr_price = price_map.get(sym)
            if not curr_price:
                continue

            target_price = float(note.get("target_price", 0.0))
            cond_type = note.get("condition_type", "CROSS_ABOVE")
            is_hit = False
            tol = target_price * 0.002

            if cond_type == "CROSS_ABOVE":
                if curr_price >= target_price:
                    is_hit = True
            elif cond_type == "CROSS_BELOW":
                if curr_price <= target_price:
                    is_hit = True
            elif cond_type == "PRICE_REACH":
                if abs(curr_price - target_price) <= tol:
                    is_hit = True

            if is_hit:
                note["is_triggered"] = True
                note["triggered_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                note["triggered_price"] = curr_price
                note["is_active"] = False
                triggered_list.append({
                    "note": note,
                    "current_price": curr_price
                })

        if triggered_list:
            self._save_notes()

        return triggered_list


# Singleton örnekleri
trade_journal_manager = TradeJournalManager()
trade_notes_manager = TradeNotesAlertManager()
