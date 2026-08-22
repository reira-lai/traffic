from hk_bus_eta import HKEta
import json
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import sys

# ========== 巴士路线配置（包含公司代号和显示名称） ==========
# 注意：公司代号需与 route_list 中的 'co' 字段匹配（除龙运外）
BUS_ROUTES = [
    {'company': 'kmb', 'route': '59X',  'display': '湖景邨湖翠樓'},
    {'company': 'kmb', 'route': '59M',  'display': '蝴蝶站'},
    {'company': 'kmb', 'route': '259D', 'display': '湖景邨湖翠樓'},
    {'company': 'ctb', 'route': '962X', 'display': '湖景邨湖畔樓'},
    {'company': 'lrtfeeder', 'route': 'K52',  'display': '蝴蝶邨蝶心樓'},  # 港铁巴士用 lrtfeeder
    {'company': 'lrtfeeder', 'route': '506',  'display': '蝴蝶邨蝶心樓'},
    # 龙运：单独处理，公司代号用 'lwb'，但 hk-bus-eta 不支持，改为直接请求
    {'company': 'lwb', 'route': 'A33',  'display': '兆山苑柳景閣'},
    {'company': 'lwb', 'route': 'E33',  'display': '兆山苑柳景閣'},
    {'company': 'lwb', 'route': 'E33P', 'display': '兆山苑柳景閣'},
    {'company': 'lwb', 'route': 'A34',  'display': '兆山苑柳景閣'},
]

# ========== 轻铁配置（站名和路线） ==========
LR_ROUTES = [
    {'station': '蝴蝶站', 'station_id': 'LR115', 'routes': ['610', '615', '615P']},
    {'station': '屯門碼頭站', 'station_id': 'LR120', 'routes': ['507', '610', '614', '614P', '615', '615P']},
]

def find_route_entry(hketa, company, route):
    """在 route_list 中查找匹配的 route_id 和完整条目"""
    for rid, info in hketa.route_list.items():
        if info['route'] == route and company in info['co']:
            return rid, info
    return None, None

def fetch_eta_with_hketa(hketa, company, route, seq=0):
    """
    使用 hk-bus-eta 的内部方法查询 ETA
    适用于 kmb, ctb, lrtfeeder, lightRail
    """
    route_id, info = find_route_entry(hketa, company, route)
    if not route_id:
        print(f"⚠️ 找不到 {company} {route} 的 route_id")
        return []

    try:
        # 根据公司类型调用对应方法
        if company == 'kmb':
            # 需要 stop_id, route, seq, service_type, co, bound
            stop_id = info['stops']['kmb'][seq]
            service_type = info['serviceType']
            co = info['co']
            bound = info['bound']['kmb']
            etas = hketa.kmb(stop_id, route, seq, service_type, co, bound)
            return etas
        elif company == 'ctb':
            stop_id = info['stops']['ctb'][seq]
            bound = info['bound']['ctb']
            etas = hketa.ctb(stop_id, route, bound, seq)
            return etas
        elif company == 'lrtfeeder':
            stop_id = info['stops']['lrtfeeder'][seq]
            etas = hketa.lrtfeeder(stop_id, route, 'zh')
            return etas
        elif company == 'lightRail':
            stop_id = info['stops']['lightRail'][seq]
            dest = info['dest']
            etas = hketa.lightrail(stop_id, route, dest)
            return etas
        else:
            print(f"⚠️ 未知公司类型: {company}")
            return []
    except Exception as e:
        print(f"❌ {company} {route} 查询错误: {e}")
        return []

def fetch_lwb_eta(route, stop_id):
    """龙运直接请求 data.hkbus.app"""
    url = f"https://data.hkbus.app/eta/lwb/{route}/{stop_id}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        else:
            return []
    except Exception as e:
        print(f"❌ 龙运 {route} 直接请求失败: {e}")
        return []

def fetch_lightrail_manual(station_id, wanted_routes):
    """手动获取轻铁数据（与 hk-bus-eta 内部逻辑相同，但直接调用）"""
    # 直接调用 hk-bus-eta 的 lightrail 方法需要构造 dest，较麻烦，我们用官方 API
    url = f"https://rt.data.gov.hk/v1/transport/mtr/lrt/getSchedule?station_id={station_id[2:]}&with_special=1"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        platform_list = data.get('platform_list', [])
        items = []
        for platform in platform_list:
            for e in platform.get('route_list', []):
                route_no = e.get('route_no')
                if route_no not in wanted_routes:
                    continue
                time_en = e.get('time_en', '').strip()
                # 解析等待分钟
                waitTime = 0
                te = time_en.lower()
                if te in ('arriving', 'departing', '-', ''):
                    waitTime = 0
                else:
                    import re
                    m = re.search(r'\d+', time_en)
                    waitTime = int(m.group()) if m else 0
                # 构造时间
                from datetime import datetime, timezone
                import time
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
        return result
    except Exception as e:
        print(f"轻铁手动请求失败: {e}")
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
    print("🚀 开始使用 hk-bus-eta 抓取数据...")
    try:
        hketa = HKEta()
    except Exception as e:
        print(f"❌ HKEta 初始化失败: {e}")
        sys.exit(1)
    print(f"✅ 已载入路线资料库，共 {len(hketa.route_list)} 条路线。")

    # 香港时区
    hk_tz = ZoneInfo("Asia/Hong_Kong")
    now_hk = datetime.now(hk_tz)

    new_result = {
        'timestamp': now_hk.isoformat(),
        'bus_items': [],
        'lr_items': []
    }

    # ---- 处理巴士 ----
    bus_ok = False
    for item in BUS_ROUTES:
        company = item['company']
        route = item['route']
        display = item['display']

        if company == 'lwb':
            # 龙运：需要站码，这里硬编码（从截图获得）
            stop_map = {'A33': 'TM436', 'E33': 'TM436', 'E33P': 'TM436', 'A34': 'TM436'}
            stop_id = stop_map.get(route, 'TM436')
            etas = fetch_lwb_eta(route, stop_id)
        else:
            # 其他公司：使用 hk-bus-eta
            etas = fetch_eta_with_hketa(hketa, company, route, seq=0)
            if not etas:
                # 尝试 seq=1
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

    # ---- 轻铁 ----
    lr_ok = False
    for station_info in LR_ROUTES:
        station_name = station_info['station']
        station_id = station_info['station_id']
        wanted = station_info['routes']
        grouped = fetch_lightrail_manual(station_id, wanted)
        for entry in grouped:
            new_result['lr_items'].append({
                'station_name': station_name,
                'route': entry['route'],
                'etas': entry['etas']
            })
            if entry['etas']:
                lr_ok = True
        print(f"轻铁 {station_name} 抓取完成，共 {len(grouped)} 条路线")

    # ---- 决定是否覆盖 ----
    if not bus_ok and not lr_ok:
        old_data = load_old_data()
        if old_data:
            print("⚠️ 本次抓取全部为空，保留上一次的 JSON 文件。")
            return
        else:
            print("⚠️ 本次抓取全部为空，且无旧文件，写入空数据。")
            save_data(new_result)
    else:
        print("✅ 本次抓取有效，写入新数据。")
        save_data(new_result)

if __name__ == '__main__':
    main()
