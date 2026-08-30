"""
CryptoSignalPro AI - Trade Günlüğü & Trade Notları ve Fiyat Alarmı Servisi (v1.0.0)

Bileşenler:
1. TradeJournalManager:
   - Kullanıcının manuel veya sinyal kaynaklı işlemlerini kaydeder.
   - Pozisyon durumu: OPEN (Açık), WIN_TP (Kâr/TP), LOSS_SL (Zarar/SL), CLOSED (Kapatıldı), CANCELLED (İptal).
   - Otomatik PnL %, Net Kâr/Zarar, Kazanma Oranı (Win Rate %), Kâr Faktörü ve R:R istatistikleri.
   - `data/trade_journal.json` üzerinde kalıcı depolama.

2. TradeNotesAlertManager:
   - Seçilen coinlerde özel hedef fiyat, analiz notları ve alarm koşulları tanımlar.
   - Koşul Türleri:
     * CROSS_ABOVE: Fiyat hedefin üstüne çıkarsa
     * CROSS_BELOW: Fiyat hedefin altına düşerse
     * PRICE_REACH: Fiyat hedefe yaklaşırsa (%0.3 tolerans)
   - Arka planda 7/24 canlı fiyat akışını takip eder.
   - Hedefe ulaşıldığında Telegram üzerinden anlık analiz notlu alarm gönderir.
   - `data/trade_notes.json` üzerinde kalıcı depolama.
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


class TradeJournalManager:
    def __init__(self):
        self.trades: List[Dict[str, Any]] = self._load_journal()

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
        position_size = float(trade_data.get("position_size", 0.0)) # USDT cinsinden büyüklük
        
        # Otomatik Risk / Ödül Oranı
        risk_dist = abs(entry_price - stop_loss) if entry_price and stop_loss else 0.0
        reward_dist = abs(target_price - entry_price) if target_price and entry_price else 0.0
        rr_ratio = round(reward_dist / risk_dist, 2) if risk_dist > 0 else 0.0

        status = trade_data.get("status", "OPEN").upper()
        exit_price = float(trade_data.get("exit_price")) if trade_data.get("exit_price") else None
        pnl_percent = 0.0
        pnl_amount = 0.0

        if exit_price and exit_price > 0 and entry_price > 0:
            if direction == "LONG":
                pnl_percent = round((exit_price - entry_price) / entry_price * 100.0, 2)
            else:
                pnl_percent = round((entry_price - exit_price) / entry_price * 100.0, 2)
            
            if position_size > 0:
                pnl_amount = round(position_size * (pnl_percent / 100.0), 2)

        if trade_data.get("entry_date_str"):
            try:
                clean_ds = str(trade_data["entry_date_str"]).replace("T", " ").strip()
                dt = datetime.strptime(clean_ds[:16], "%Y-%m-%d %H:%M")
                now = dt.timestamp()
            except Exception:
                pass

        new_trade = {
            "id": trade_id,
            "symbol": trade_data.get("symbol", "BTC/USDT").upper().strip(),
            "direction": direction,
            "entry_price": entry_price,
            "target_price": target_price,
            "stop_loss": stop_loss,
            "exit_price": exit_price,
            "status": status, # OPEN, WIN_TP, LOSS_SL, CLOSED, CANCELLED
            "risk_reward": rr_ratio,
            "position_size": position_size,
            "pnl_percent": pnl_percent,
            "pnl_amount": pnl_amount,
            "strategy": trade_data.get("strategy", "Kişisel Analiz"),
            "notes": trade_data.get("notes", ""),
            "entry_date_str": trade_data.get("entry_date_str") or datetime.now().strftime("%Y-%m-%d %H:%M"),
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
                    except Exception:
                        pass
                
                # PnL'i güncelle
                entry_price = float(trade.get("entry_price", 0.0))
                exit_price = float(trade.get("exit_price", 0.0)) if trade.get("exit_price") else None
                direction = trade.get("direction", "LONG")
                position_size = float(trade.get("position_size", 0.0))

                if exit_price and exit_price > 0 and entry_price > 0:
                    if direction == "LONG":
                        trade["pnl_percent"] = round((exit_price - entry_price) / entry_price * 100.0, 2)
                    else:
                        trade["pnl_percent"] = round((entry_price - exit_price) / entry_price * 100.0, 2)
                    
                    if position_size > 0:
                        trade["pnl_amount"] = round(position_size * (trade["pnl_percent"] / 100.0), 2)
                
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
        """Tüm işlemlerin profesyonel performans karnesini hesaplar."""
        total_trades = len(self.trades)
        if total_trades == 0:
            return {
                "total_trades": 0,
                "open_trades": 0,
                "closed_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl_pct": 0.0,
                "total_pnl_amount": 0.0,
                "avg_rr": 0.0,
                "profit_factor": 0.0,
                "best_trade_pnl": 0.0,
                "worst_trade_pnl": 0.0
            }

        open_trades = [t for t in self.trades if t.get("status") == "OPEN"]
        closed_trades = [t for t in self.trades if t.get("status") in ["WIN_TP", "LOSS_SL", "CLOSED"]]

        wins = [t for t in closed_trades if t.get("pnl_percent", 0.0) > 0 or t.get("status") == "WIN_TP"]
        losses = [t for t in closed_trades if t.get("pnl_percent", 0.0) < 0 or t.get("status") == "LOSS_SL"]

        win_rate = round(len(wins) / len(closed_trades) * 100.0, 1) if closed_trades else 0.0
        total_pnl_pct = round(sum(t.get("pnl_percent", 0.0) for t in closed_trades), 2)
        total_pnl_amount = round(sum(t.get("pnl_amount", 0.0) for t in closed_trades), 2)
        avg_rr = round(sum(t.get("risk_reward", 0.0) for t in self.trades) / total_trades, 2)

        gross_profit = sum(t.get("pnl_amount", 0.0) for t in wins if t.get("pnl_amount", 0.0) > 0)
        gross_loss = abs(sum(t.get("pnl_amount", 0.0) for t in losses if t.get("pnl_amount", 0.0) < 0))
        
        if gross_loss > 0:
            profit_factor = round(gross_profit / gross_loss, 2)
        else:
            profit_factor = round(gross_profit, 2) if gross_profit > 0 else 1.0

        pnl_list = [t.get("pnl_percent", 0.0) for t in closed_trades]
        best_trade_pnl = max(pnl_list) if pnl_list else 0.0
        worst_trade_pnl = min(pnl_list) if pnl_list else 0.0

        return {
            "total_trades": total_trades,
            "open_trades": len(open_trades),
            "closed_trades": len(closed_trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": win_rate,
            "total_pnl_pct": total_pnl_pct,
            "total_pnl_amount": total_pnl_amount,
            "avg_rr": avg_rr,
            "profit_factor": profit_factor,
            "best_trade_pnl": best_trade_pnl,
            "worst_trade_pnl": worst_trade_pnl
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

        # Eğer created_price verilmediyse anlık fiyattan al
        if created_price <= 0:
            try:
                df = market_manager.get_market_data(symbol, timeframe="1h", limit=5)
                if df is not None and len(df) > 0:
                    created_price = float(df['close'].iloc[-1])
            except Exception:
                created_price = target_price

        # Şart tipi: CROSS_ABOVE, CROSS_BELOW, PRICE_REACH
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
                    # Yeniden aktif edildiğinde tetiklenme durumunu sıfırla
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
        """
        Arka planda çalışan canlı fiyat kontrolcüsü.
        Aktif ve henüz tetiklenmemiş notları kontrol eder.
        """
        active_notes = [n for n in self.notes if n.get("is_active", True) and not n.get("is_triggered", False)]
        if not active_notes:
            return []

        triggered_list = []
        # Benzersiz coin listesini topla
        symbols = list(set(n["symbol"] for n in active_notes))

        price_map = {}
        for sym in symbols:
            try:
                df = market_manager.get_market_data(sym, timeframe="15m", limit=5)
                if df is not None and len(df) > 0:
                    price_map[sym] = float(df['close'].iloc[-1])
            except Exception:
                pass

        now = time.time()
        for note in active_notes:
            sym = note["symbol"]
            curr_price = price_map.get(sym)
            if not curr_price:
                continue

            target_price = float(note.get("target_price", 0.0))
            cond_type = note.get("condition_type", "CROSS_ABOVE")
            is_hit = False

            # Tolerans bandı (%0.20)
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
                note["is_active"] = False # Tetiklendikten sonra pasife al
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
