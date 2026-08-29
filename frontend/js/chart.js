// TradingView Lightweight Charts V4 Gelişmiş Grafik, Setup, Üçgen Formasyonları ve Pozisyon Çizici
let chartInstance = null;
let candleSeries = null;
let volumeSeries = null;
let ema20Series = null;
let ema50Series = null;
let ema200Series = null;
let profitAreaSeries = null;
let lossAreaSeries = null;
let patternLineSeriesList = [];
let activePriceLines = [];

function initTradingViewChart(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (chartInstance) {
        try {
            chartInstance.remove();
        } catch (e) {
            console.error('Error removing chart instance:', e);
        }
        chartInstance = null;
    }
    container.innerHTML = '';
    patternLineSeriesList = [];

    const width = container.clientWidth || 900;
    const height = container.clientHeight || 480;

    const chartOptions = {
        width: width,
        height: height,
        layout: {
            background: { type: 'solid', color: '#080c14' },
            textColor: '#94a3b8',
            fontSize: 12,
            fontFamily: "'JetBrains Mono', monospace",
        },
        grid: {
            vertLines: { color: 'rgba(30, 41, 59, 0.45)' },
            horzLines: { color: 'rgba(30, 41, 59, 0.45)' },
        },
        crosshair: {
            mode: 1, // Magnet crosshair
            vertLine: {
                color: '#6366f1',
                width: 1,
                style: 3,
                labelBackgroundColor: '#4f46e5',
            },
            horzLine: {
                color: '#6366f1',
                width: 1,
                style: 3,
                labelBackgroundColor: '#4f46e5',
            },
        },
        rightPriceScale: {
            borderColor: '#1e293b',
            scaleMargins: {
                top: 0.12,
                bottom: 0.22,
            },
            autoScale: true,
        },
        timeScale: {
            borderColor: '#1e293b',
            timeVisible: true,
            secondsVisible: false,
            fixLeftEdge: true,
            rightOffset: 10,
        },
    };

    chartInstance = LightweightCharts.createChart(container, chartOptions);

    // 1. Pozisyon Kâr & Zarar Gölgelendirme Alanları (TradingView Long/Short Position Box)
    profitAreaSeries = chartInstance.addAreaSeries({
        topColor: 'rgba(16, 185, 129, 0.22)',
        bottomColor: 'rgba(16, 185, 129, 0.02)',
        lineColor: 'rgba(16, 185, 129, 0.6)',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
    });

    lossAreaSeries = chartInstance.addAreaSeries({
        topColor: 'rgba(239, 68, 68, 0.02)',
        bottomColor: 'rgba(239, 68, 68, 0.22)',
        lineColor: 'rgba(239, 68, 68, 0.6)',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
    });

    // 2. Hacim Histogramı
    volumeSeries = chartInstance.addHistogramSeries({
        color: 'rgba(99, 102, 241, 0.25)',
        priceFormat: {
            type: 'volume',
        },
        priceScaleId: '',
        scaleMargins: {
            top: 0.80,
            bottom: 0,
        },
    });

    // 3. EMA Ribbon Çizgileri
    ema20Series = chartInstance.addLineSeries({
        color: '#f59e0b',
        lineWidth: 1.5,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
    });

    ema50Series = chartInstance.addLineSeries({
        color: '#06b6d4',
        lineWidth: 1.5,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
    });

    ema200Series = chartInstance.addLineSeries({
        color: '#a855f7',
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
    });

    // 4. Ana Mum Serisi
    candleSeries = chartInstance.addCandlestickSeries({
        upColor: '#10b981',
        downColor: '#ef4444',
        borderVisible: false,
        wickUpColor: '#10b981',
        wickDownColor: '#ef4444',
    });

    // Crosshair Takibi
    chartInstance.subscribeCrosshairMove((param) => {
        if (!param || !param.time || !param.seriesPrices) return;
        const candlePrice = param.seriesPrices.get(candleSeries);
        if (candlePrice) {
            const hudPrice = document.getElementById('hudPrice');
            if (hudPrice) {
                hudPrice.textContent = `$${formatPrice(candlePrice.close)}`;
            }
        }
    });

    // Resize Handler
    window.addEventListener('resize', () => {
        if (chartInstance && container) {
            chartInstance.applyOptions({
                width: container.clientWidth,
                height: container.clientHeight
            });
        }
    });
}

function renderChartData(chartData) {
    if (!chartInstance || !candleSeries) return;

    // Önceki seviye çizgilerini ve formasyon çizgilerini temizle
    activePriceLines.forEach(pl => {
        try {
            candleSeries.removePriceLine(pl);
        } catch (e) {}
    });
    activePriceLines = [];

    patternLineSeriesList.forEach(s => {
        try {
            chartInstance.removeSeries(s);
        } catch (e) {}
    });
    patternLineSeriesList = [];

    // 1. Mum Verilerini Yükle
    const rawCandles = chartData.candles || [];
    if (rawCandles.length === 0) return;

    const candles = rawCandles.map(c => ({
        time: c.time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close
    }));
    candleSeries.setData(candles);

    // 2. Hacim Verilerini Yükle
    if (volumeSeries) {
        const volumes = rawCandles.map(c => ({
            time: c.time,
            value: c.volume,
            color: c.close >= c.open ? 'rgba(16, 185, 129, 0.25)' : 'rgba(239, 68, 68, 0.25)'
        }));
        volumeSeries.setData(volumes);
    }

    // 3. EMA Verilerini Yükle
    if (chartData.emas) {
        if (ema20Series && chartData.emas.ema20) ema20Series.setData(chartData.emas.ema20);
        if (ema50Series && chartData.emas.ema50) ema50Series.setData(chartData.emas.ema50);
        if (ema200Series && chartData.emas.ema200) ema200Series.setData(chartData.emas.ema200);
    }

    const setup = chartData.setup;
    if (setup) {
        const isLong = setup.direction === 'LONG';
        const lastCandle = candles[candles.length - 1];

        // 4. Pozisyon Kutu Gölgelendirmesi (TradingView Position Box Shading)
        // Son 25 bar boyunca Kâr ve Zarar bölgelerini renkli gölgele
        const boxLookback = Math.min(25, candles.length);
        const boxCandles = candles.slice(-boxLookback);
        
        if (isLong) {
            const profitData = boxCandles.map(c => ({ time: c.time, value: setup.tp2 }));
            const lossData = boxCandles.map(c => ({ time: c.time, value: setup.stop_loss }));
            profitAreaSeries.setData(profitData);
            lossAreaSeries.setData(lossData);
        } else {
            const profitData = boxCandles.map(c => ({ time: c.time, value: setup.tp2 }));
            const lossData = boxCandles.map(c => ({ time: c.time, value: setup.stop_loss }));
            profitAreaSeries.setData(profitData);
            lossAreaSeries.setData(lossData);
        }

        // 5. Sinyal Giriş Oku (Signal Marker)
        const markers = [];
        if (lastCandle) {
            markers.push({
                time: lastCandle.time,
                position: isLong ? 'belowBar' : 'aboveBar',
                color: isLong ? '#10b981' : '#f43f5e',
                shape: isLong ? 'arrowUp' : 'arrowDown',
                text: isLong ? `🟢 LONG GİRİŞ ($${formatPrice(setup.entry_price)})` : `🔴 SHORT GİRİŞ ($${formatPrice(setup.entry_price)})`,
                size: 2,
            });
        }
        candleSeries.setMarkers(markers);

        // 6. GİRİŞ Çizgisi (Parlak Camgöbeği - Cyan)
        const entryLine = candleSeries.createPriceLine({
            price: setup.entry_price,
            color: '#38bdf8',
            lineWidth: 2,
            lineStyle: 0,
            axisLabelVisible: true,
            title: '🎯 GİRİŞ (ENTRY)',
        });
        activePriceLines.push(entryLine);

        // 7. STOP LOSS Çizgisi (Parlak Kırmızı)
        const slLine = candleSeries.createPriceLine({
            price: setup.stop_loss,
            color: '#f43f5e',
            lineWidth: 2,
            lineStyle: 2,
            axisLabelVisible: true,
            title: `🛑 STOP (-%${setup.risk_percent})`,
        });
        activePriceLines.push(slLine);

        // 8. TP1 Çizgisi
        const tp1Line = candleSeries.createPriceLine({
            price: setup.tp1,
            color: '#34d399',
            lineWidth: 1,
            lineStyle: 2,
            axisLabelVisible: true,
            title: `🏆 TP1 (+%${setup.reward_tp1_percent})`,
        });
        activePriceLines.push(tp1Line);

        // 9. TP2 Çizgisi (Ana Hedef)
        const tp2Line = candleSeries.createPriceLine({
            price: setup.tp2,
            color: '#10b981',
            lineWidth: 2,
            lineStyle: 0,
            axisLabelVisible: true,
            title: `🚀 TP2 (+%${setup.reward_tp2_percent})`,
        });
        activePriceLines.push(tp2Line);

        // 10. TP3 Çizgisi (Trend Devamı)
        const tp3Line = candleSeries.createPriceLine({
            price: setup.tp3,
            color: '#059669',
            lineWidth: 2,
            lineStyle: 1,
            axisLabelVisible: true,
            title: `⭐ TP3 (+%${setup.reward_tp3_percent})`,
        });
        activePriceLines.push(tp3Line);

        // 11. ÜÇGEN VE FORMASYON ÇİZGİLERİ (Trendlines Çizimi)
        if (chartData.patterns && chartData.patterns.length > 0) {
            chartData.patterns.forEach(pat => {
                // Eğer formasyona ait özel trendline koordinatları varsa doğrudan grafik üzerine çiz
                if (pat.lines && Array.isArray(pat.lines)) {
                    pat.lines.forEach(lineDef => {
                        const patLineSeries = chartInstance.addLineSeries({
                            color: lineDef.color || '#fbbf24',
                            lineWidth: 2,
                            lineStyle: 2,
                            priceLineVisible: false,
                            lastValueVisible: false,
                            crosshairMarkerVisible: false,
                        });
                        patLineSeries.setData(lineDef.points);
                        patternLineSeriesList.push(patLineSeries);
                    });
                }

                // Boyun Çizgisi
                if (pat.neckline) {
                    const neckLine = candleSeries.createPriceLine({
                        price: pat.neckline,
                        color: '#fbbf24',
                        lineWidth: 1.5,
                        lineStyle: 2,
                        axisLabelVisible: false,
                        title: `📐 ${pat.name.split(' ')[0]} BOYUN ÇİZGİSİ`,
                    });
                    activePriceLines.push(neckLine);
                }

                // Formasyon Hedefi
                if (pat.target) {
                    const patTargetLine = candleSeries.createPriceLine({
                        price: pat.target,
                        color: '#f59e0b',
                        lineWidth: 1.5,
                        lineStyle: 3,
                        axisLabelVisible: false,
                        title: `🎯 FORMASYON HEDEFİ ($${formatPrice(pat.target)})`,
                    });
                    activePriceLines.push(patTargetLine);
                }

                // Fibonacci Golden Pocket
                if (pat.golden_zone) {
                    const fibLine = candleSeries.createPriceLine({
                        price: pat.golden_zone[1],
                        color: '#f59e0b',
                        lineWidth: 1.5,
                        lineStyle: 3,
                        axisLabelVisible: false,
                        title: `🟡 FIB 0.618-0.65 POCKET`,
                    });
                    activePriceLines.push(fibLine);
                }
            });
        }

        // 12. SMC Order Block & FVG Seviyeleri
        if (chartData.smc) {
            if (chartData.smc.active_obs && chartData.smc.active_obs.length > 0) {
                const ob = chartData.smc.active_obs[0];
                const obColor = ob.type === 'BULLISH_OB' ? 'rgba(16, 185, 129, 0.8)' : 'rgba(239, 68, 68, 0.8)';
                const obTopLine = candleSeries.createPriceLine({
                    price: ob.top,
                    color: obColor,
                    lineWidth: 1,
                    lineStyle: 3,
                    axisLabelVisible: false,
                    title: `📦 ${ob.type === 'BULLISH_OB' ? 'BULLISH' : 'BEARISH'} ORDER BLOCK`,
                });
                activePriceLines.push(obTopLine);
            }

            if (chartData.smc.active_fvgs && chartData.smc.active_fvgs.length > 0) {
                const fvg = chartData.smc.active_fvgs[0];
                const fvgColor = fvg.type === 'BULLISH_FVG' ? 'rgba(56, 189, 248, 0.8)' : 'rgba(244, 63, 94, 0.8)';
                const fvgMidLine = candleSeries.createPriceLine({
                    price: fvg.mid,
                    color: fvgColor,
                    lineWidth: 1,
                    lineStyle: 2,
                    axisLabelVisible: false,
                    title: `⚡ FVG %50 DENGE`,
                });
                activePriceLines.push(fvgMidLine);
            }
        }
    }

    setTimeout(() => {
        if (chartInstance) {
            chartInstance.timeScale().fitContent();
        }
    }, 50);
}

function fitModalChart() {
    if (chartInstance) {
        chartInstance.timeScale().fitContent();
    }
}
