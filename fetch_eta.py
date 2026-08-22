from hk_bus_eta import HKEta
import json
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import sys
import re
import time

# ============================================================
# 配置：巴士路線（站名保持原樣）
# ============================================================
BUS_ROUTES = [
    {'company': 'lrtfeeder', 'route': 'K52',  'display': '蝴蝶邨蝶心樓'},
    {'company': 'lrtfeeder', 'route': '506',  'display': '蝴蝶邨蝶心樓'},
    {'company': 'kmb', 'route': '59X',  'display': '湖景邨湖翠樓'},
    {'company': 'kmb', 'route': '59M',  'display': '蝴蝶站'},
    {'company': 'kmb', 'route': '259D', 'display': '湖景邨湖翠樓'},
    {'company': 'ctb', 'route': '962X', 'display': '湖景邨湖畔樓'},
    {'company': 'lwb', 'route': 'A33',  'display': '兆山苑柳景閣'},
    {'company': 'lwb', 'route': 'E33',  'display': '兆山苑柳景閣'},
    {'company': 'lwb', 'route': 'E33P', 'display': '兆山苑柳景閣'},
    {'company': 'lwb', 'route': 'A34',  'display': '兆山苑柳景閣'},
]

# ============================================================
# 配置：輕鐵（美樂站使用正確的 station_id: LR010）
# ============================================================
LR_ROUTES = [
    {'station': '美樂站', 'station_id': 'LR010', 'routes': ['610', '615', '615P']},
    {'station': '屯門碼頭站', 'station_id': 'LR120', 'routes': ['507', '610', '614', '614P', '615', '615P']},
]

# ============================================================
# 輔助函數
# ============================================================
def find_route_entry(hketa, company, route):
    for rid, info in hketa.route_list.items():
        if info['route'] == route and company in info['co']:
            return rid, info
    return None, None

def fetch_eta_with_hketa(hketa, company, route, seq=0):
    route_id, info = find_route_entry(hketa, company, route)
    if not route_id:
        print(f"⚠️ 找不到 {company} {route} 的 route_id")
        return []
    try:
        if company == 'kmb':
            stop_id = info['stops']['kmb'][seq]
            service_type = info['serviceType']
            co = info['co']
            bound = info['bound']['kmb']
            return hketa.kmb(stop_id, route, seq, service_type, co, bound)
        elif company == 'ctb':
            stop_id = info['stops']['ctb'][seq]
            bound = info['bound']['ctb']
            return hketa.ctb(stop_id, route, bound, seq)
        elif company == 'lrtfeeder':
            stop_id = info['stops']['lrtfeeder'][seq]
            return hketa.lrtfeeder(stop_id, route, 'zh')
        else:
            return []
    except Exception as e:
        print(f"❌ {company} {route} 查詢錯誤: {e}")
        return []

def fetch_lwb_eta(route, stop_id):
    """龍運直接請求 data.hkbus.app，使用 TM464（美樂花園）"""
    url = f"https://data.hkbus.app/eta/lwb/{route}/{stop_id}"
    print(f"  龍運請求: {url}")
    try:
        resp = requests.get(url, timeout=10)
        print(f"  龍運響應狀態: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  龍運返回數據量: {len(data) if data else 0}")
            if not data:
                alt_url = f"https://data.hkbus.app/eta/lwb/{route}"
                print(f"  嘗試備用請求: {alt_url}")
                alt_resp = requests.get(alt_url, timeout=10)
                if alt_resp.status_code == 200:
                    alt_data = alt_resp.json()
                    print(f"  備用返回數據量: {len(alt_data) if alt_data else 0}")
                    return alt_data
            return data
        else:
            print(f"  龍運響應內容: {resp.text[:200]}")
            return []
    except Exception as e:
        print(f"❌ 龍運 {route} 直接請求失敗: {e}")
        return []

def fetch_lightrail_manual(station_id, wanted_routes):
    """手動抓取輕鐵，station_id 格式如 LR010 -> 010"""
    # 去掉 "LR" 前綴
    clean_id = station_id[2:] if station_id.startswith('LR') else station_id
    url = f"https://rt.data.gov.hk/v1/transport/mtr/lrt/getSchedule?station_id={clean_id}&with_special=1"
    print(f"  輕鐵請求: {url}")
    try:
        resp = requests.get(url, timeout=10)
        print(f"  輕鐵響應狀態: {resp.status_code}")
        if resp.status_code != 200:
            print(f"  輕鐵響應內容: {resp.text[:200]}")
            return []
        data = resp.json()
        platform_list = data.get('platform_list', [])
        print(f"  輕鐵平台數: {len(platform_list)}")
        items = []
        for platform in platform_list:
            for e in platform.get('route_list', []):
                route_no = e.get('route_no')
                if route_no not in wanted_routes:
                    continue
                time_en = e.get('time_en', '').strip()
                waitTime = 0
                te = time_en.lower()
                if te in ('arriving', 'departing', '-', ''):
                    waitTime = 0
                else:
                    m = re.search(r'\d+', time_en)
                    waitTime = int(m.group()) if m else 0
                dt = datetime.fromtimestamp(time.time() + waitTime * 60 + 8 * 3600)
                eta_str = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+08:00")
                items.append({'route': route_no, 'eta': eta_str})
        # 按路线分组
        grouped = {}
        for item in items:
            grouped.setdefault(item['route'], []).append(item['eta'])
        result = []
        for route, times in grouped.items():
            times.sort()
            result.append({
                'route': route,
                'etas': [{'eta': t} for t in times[:3]]
            })
        print(f"  輕鐵抓取結果: {len(result)} 條路線有數據")
        return result
    except Exception as e:
        print(f"輕鐵手動請求失敗: {e}")
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

# ============================================================
# 主程式
# ============================================================
def main():
    print("🚀 開始抓取數據...")
    try:
        hketa = HKEta()
    except Exception as e:
        print(f"❌ HKEta 初始化失敗: {e}")
        sys.exit(1)
    print(f"✅ 已載入路線資料庫，共 {len(hketa.route_list)} 條路線。")

    hk_tz = ZoneInfo("Asia/Hong_Kong")
    now_hk = datetime.now(hk_tz)

    new_result = {
        'timestamp': now_hk.isoformat(),
        'bus_items': [],
        'lr_items': []
    }

    # ---- 抓取巴士 ----
    bus_ok = False
    for item in BUS_ROUTES:
        company = item['company']
        route = item['route']
        display = item['display']

        if company == 'lwb':
            stop_map = {'A33': 'TM464', 'E33': 'TM464', 'E33P': 'TM464', 'A34': 'TM464'}
            stop_id = stop_map.get(route, 'TM464')
            etas = fetch_lwb_eta(route, stop_id)
        else:
            etas = fetch_eta_with_hketa(hketa, company, route, seq=0)
            if not etas:
                etas = fetch_eta_with_hketa(hketa, company, route, seq=1)

        new_result['bus_items'].append({
            'company': company,
            'route': route,
            'display_name': display,
            'etas': etas
        })
        if etas:
            bus_ok = True
        print(f"巴士 {company} {route} at {display} -> {len(etas)} 班次")

    # ---- 抓取輕鐵 ----
    lr_ok = False
    for station_info in LR_ROUTES:
        station = station_info['station']
        station_id = station_info['station_id']
        wanted = station_info['routes']
        grouped = fetch_lightrail_manual(station_id, wanted)
        for entry in grouped:
            new_result['lr_items'].append({
                'station_name': station,
                'route': entry['route'],
                'etas': entry['etas']
            })
            if entry['etas']:
                lr_ok = True
        print(f"輕鐵 {station} 抓取完成，共 {len(grouped)} 條路線有數據")

    # ---- 保存 ----
    if not bus_ok and not lr_ok:
        old_data = load_old_data()
        if old_data:
            print("⚠️ 本次抓取全部為空，保留上一次的 JSON 文件。")
            return
        else:
            print("⚠️ 本次抓取全部為空，寫入空數據。")
            save_data(new_result)
    else:
        print("✅ 本次抓取有效，寫入新數據。")
        save_data(new_result)

if __name__ == '__main__':
    main()
