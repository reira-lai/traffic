from hk_bus_eta import HKEta
import json
from datetime import datetime
import requests

# 你要查詢的路線清單（公司代號：路線號碼）
WANTED_ROUTES = {
    'kmb': ['59X', '59M', '59A', 'N260', '259B', '59S'],
    'lwb': ['A33'],
    'ctb': ['962X', '962P', 'B3'],
    'mtr': ['K52', '506']
}

def find_route_id(hketa, company, route):
    """在 route_list 中尋找符合公司與路線號碼的 route_id"""
    for rid, info in hketa.route_list.items():
        if info['route'] == route and company in info['co']:
            return rid
    return None

def fetch_lightrail(station_id='120'):
    """輕鐵使用官方 API"""
    url = f"https://rt.data.gov.hk/v1/transport/mtr/lrt/getSchedule?station_id={station_id}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            etas = []
            for p in data.get('platform', []):
                for r in p.get('routeList', []):
                    for t in r.get('trains', []):
                        if 'time' in t:
                            etas.append({'eta': t['time']})
            etas.sort(key=lambda x: x['eta'])
            return etas[:10]
        else:
            return []
    except Exception as e:
        print(f"Error fetching lightrail: {e}")
        return []

def main():
    print("🚀 開始抓取 ETA 數據...")
    hketa = HKEta()
    print(f"✅ 已載入路線資料庫，共 {len(hketa.route_list)} 條路線。")

    result = {
        'timestamp': datetime.now().isoformat(),
        'bus': {},
        'lightrail': []
    }

    # 處理每間公司的路線
    for company, routes in WANTED_ROUTES.items():
        result['bus'][company] = {}
        for route in routes:
            route_id = find_route_id(hketa, company, route)
            if route_id:
                try:
                    etas = hketa.getEtas(route_id=route_id, seq=0, language='zh')
                    result['bus'][company][route] = etas
                    print(f"✅ {company} {route} 獲取成功，共 {len(etas)} 筆班次")
                except Exception as e:
                    print(f"❌ {company} {route} 查詢錯誤: {e}")
                    result['bus'][company][route] = []
            else:
                print(f"⚠️ 找不到 {company} {route} 的 route_id")
                result['bus'][company][route] = []

    # 輕鐵
    print("🚈 獲取輕鐵數據...")
    result['lightrail'] = fetch_lightrail('120')

    # 寫入 JSON
    with open('eta-data.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("✅ ETA 數據已寫入 eta-data.json")

if __name__ == '__main__':
    main()
