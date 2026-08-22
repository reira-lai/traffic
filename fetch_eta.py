from hk_bus_eta import HKEta
import json
from datetime import datetime
from zoneinfo import ZoneInfo

# ========== 巴士路線（只保留你截圖中的站名與公司） ==========
# 注意：這裡的 'display' 只是前端顯示用，實際站點由 route_id 決定
BUS_ROUTES = [
    {'company': 'kmb', 'route': '59X',  'display': '湖景邨湖翠樓'},
    {'company': 'kmb', 'route': '59M',  'display': '蝴蝶站'},
    {'company': 'kmb', 'route': '259D', 'display': '湖景邨湖翠樓'},
    {'company': 'lwb', 'route': 'A33',  'display': '兆山苑柳景閣'},
    {'company': 'lwb', 'route': 'E33',  'display': '兆山苑柳景閣'},
    {'company': 'lwb', 'route': 'E33P', 'display': '兆山苑柳景閣'},
    {'company': 'lwb', 'route': 'A34',  'display': '兆山苑柳景閣'},
    {'company': 'ctb', 'route': '962X', 'display': '湖景邨湖畔樓'},
    {'company': 'mtr', 'route': 'K52',  'display': '蝴蝶邨蝶心樓'},
    {'company': 'mtr', 'route': '506',  'display': '蝴蝶邨蝶心樓'},
]

# ========== 輕鐵路線（直接在 route_list 中查找） ==========
LR_ROUTES = [
    {'station': '蝴蝶站', 'routes': ['610', '615', '615P']},
    {'station': '屯門碼頭站', 'routes': ['507', '610', '614', '614P', '615', '615P']},
]

def find_route_id(hketa, company, route):
    """在 hketa.route_list 中尋找匹配的 route_id"""
    for rid, info in hketa.route_list.items():
        if info['route'] == route and company in info['co']:
            return rid
    return None

def fetch_eta_with_hketa(hketa, company, route, seq=0):
    """
    使用 hk-bus-eta 查詢某路線的 ETA
    seq: 0 表示去程，1 表示回程（輕鐵通常為 0）
    """
    route_id = find_route_id(hketa, company, route)
    if not route_id:
        print(f"⚠️ 找不到 {company} {route} 的 route_id")
        # 列出可能的 candidates 方便除錯
        candidates = [rid for rid, info in hketa.route_list.items() if info['route'] == route]
        if candidates:
            print(f"   可能的 route_id: {candidates}")
        return []
    try:
        etas = hketa.getEtas(route_id=route_id, seq=seq, language='zh')
        return etas
    except Exception as e:
        print(f"❌ {company} {route} 查詢錯誤: {e}")
        return []

def load_old_data(filename='eta-data.json'):
    import os
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None
    return None

def save_data(data, filename='eta-data.json'):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    print("🚀 開始使用 hk-bus-eta 抓取數據...")
    hketa = HKEta()
    print(f"✅ 已載入路線資料庫，共 {len(hketa.route_list)} 條路線。")

    # 香港時區
    hk_tz = ZoneInfo("Asia/Hong_Kong")
    now_hk = datetime.now(hk_tz)

    new_result = {
        'timestamp': now_hk.isoformat(),
        'bus_items': [],
        'lr_items': []
    }

    # ---- 抓取巴士（seq=0 去程） ----
    bus_ok = False
    for item in BUS_ROUTES:
        company = item['company']
        route = item['route']
        display = item['display']
        etas = fetch_eta_with_hketa(hketa, company, route, seq=0)
        new_result['bus_items'].append({
            'company': company,
            'route': route,
            'display_name': display,
            'etas': etas
        })
        if etas:
            bus_ok = True
        print(f"巴士 {company} {route} at {display} -> {len(etas)} 班次")

    # ---- 抓取輕鐵（同樣使用 hk-bus-eta） ----
    lr_ok = False
    for station_info in LR_ROUTES:
        station_name = station_info['station']
        for route in station_info['routes']:
            # 輕鐵的公司代號通常為 'lightRail'，但可能也為 'mtr'，先嘗試 'lightRail'
            # 根據 hk-bus-eta 的 route_list，輕鐵的 co 可能是 ['lightRail']
            etas = fetch_eta_with_hketa(hketa, 'lightRail', route, seq=0)
            # 如果找不到，嘗試 'mtr' 作為備用
            if not etas:
                etas = fetch_eta_with_hketa(hketa, 'mtr', route, seq=0)
            new_result['lr_items'].append({
                'station_name': station_name,
                'route': route,
                'etas': etas
            })
            if etas:
                lr_ok = True
            print(f"輕鐵 {route} at {station_name} -> {len(etas)} 班次")

    # ---- 決定是否覆蓋 ----
    if not bus_ok and not lr_ok:
        old_data = load_old_data()
        if old_data:
            print("⚠️ 本次抓取全部為空，保留上一次的 JSON 文件。")
            return
        else:
            print("⚠️ 本次抓取全部為空，且無舊文件，寫入空數據。")
            save_data(new_result)
    else:
        print("✅ 本次抓取有效，寫入新數據。")
        save_data(new_result)

if __name__ == '__main__':
    main()
