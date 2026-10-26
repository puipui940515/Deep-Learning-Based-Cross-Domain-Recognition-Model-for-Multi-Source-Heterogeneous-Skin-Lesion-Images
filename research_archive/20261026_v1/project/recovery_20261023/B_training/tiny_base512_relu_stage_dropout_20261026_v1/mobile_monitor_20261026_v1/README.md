# 手機唯讀即時監控

2026-10-26T15:23:42.834561+08:00 啟動，僅讀取既有正式MONITOR.md；原訓練程式／契約／配置均未修改。每15秒由手機頁面重新取得同一監控表；表格可左右滑動，來源超過60秒未更新會提示。標準庫CPU服務，不載入模型、不使用GPU、不提供寫入或訓練控制；只綁定目前LAN IP，無目錄瀏覽、資料／權重下載或外部資源。

手機連接與電腦相同路由器Wi-Fi後開啟：http://192.168.1.101:8768/fpbz5xX-h0jjm5f1fDHdOo7QEoP53XPq/

服務PID：3608（venv外層28260）。僅本機對LAN IP的HTTP200、內容／15秒刷新／手機viewport及未授權路徑404已驗證，實體手機未驗證。沒有改Windows、防火牆或路由器，若手機無法連線，可能受防火牆或Wi-Fi裝置隔離影響；此服務不支援外出行動網路。

停止只影響此監控服務（先核對PID仍對應serve_monitor.py）：Stop-Process -Id 3608。不停止controller、trainer或F服務。若IP變動需更新連結，電腦需持續開機。存取連結含隨機識別碼，請只供本人查看。詳細本機驗證LOCAL_VALIDATION.json，啟動SERVER_RECEIPT.json。

## 外出行動網路入口

2026-10-26T15:48:29.507661+08:00：依使用者明確要求外出行動網路可看，透過Windows既有OpenSSH、localhost.run免費臨時TLS tunnel，僅轉送原監控服務192.168.1.101:8768。未改訓練／F網站／Windows／防火牆／路由器，未安裝下載、未使用本機私人SSH identity。

手機網址：https://b02e24fabee0a0.lhr.life/fpbz5xX-h0jjm5f1fDHdOo7QEoP53XPq/

公開HTTPS往返200、內容Run ID、15秒刷新及根目錄／AGENTS.md／MONITOR.md均404已驗證；實體手機行動網路尚未由使用者測試。第三方服務終止TLS，能處理監控流量；只轉送監控頁，無資料圖片／權重／控制入口。請只本人保留完整隨機存取連結。免費域名可能變動／斷線，電腦與監控及ssh需持續運作，不宣稱永久連結。停止此外網轉送：先核對PID17180仍為本tunnel之ssh再Stop-Process -Id 17180；不停止訓練。完整命令TUNNEL_START.json、驗證REMOTE_VALIDATION.json。

## 外網連線第一次修復

2026-10-26T16:51:07.161555+08:00：原SSH17180因上游明確回報tunnel activity timeout退出，舊域名HTTP502。本機監控HTTP200、訓練controller正常，Tiny1已完成30輪／Tiny2進行中，均未重啟。僅建立一次新SSH PID15484；新HTTPS入口 https://a4d79e1e50e115.lhr.life/fpbz5xX-h0jjm5f1fDHdOo7QEoP53XPq/ 已HTTP200驗證。新增60秒只讀HTTP保活，固定綁定此SSH程序handle；程序退出或健康檢查失敗即記錄停止，不重連、不循環啟動研究。沒有修改Windows／防火牆／資料／模型／trainer／核定來源。
