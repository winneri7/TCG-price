import streamlit as st
import pandas as pd
from curl_cffi import requests as crequests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import os
import re
import time
from datetime import datetime
import plotly.express as px
from urllib.parse import quote

# --- [CORE] DATA STORAGE ---
DATA_FILE = "tcg_master_db.csv"
HISTORY_FILE = "tcg_price_history.csv"

# --- 1. SYSTEM CONFIGURATION ---
GAMES = ["포켓몬", "원피스", "바이스슈발츠"]
WEISS_ORDER = ["니케", "벽람항로", "렌탈여친", "데이트 어 라이브", "오버로드", "체리", "블루 아카이브", "최애의 아이", "키", "기타"]
GAME_URLS = {"포켓몬": "https://yuyu-tei.jp/sell/poc/s/search", "원피스": "https://yuyu-tei.jp/sell/opc/s/search", "바이스슈발츠": "https://yuyu-tei.jp/sell/ws/s/search"}
translator = GoogleTranslator(source='ja', target='ko')

# --- 2. DATA ENGINE (MIGRATION ADDED) ---
def load_data():
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame(columns=["card_id", "game", "sub_category", "last_price", "image_url", "stock", "title", "title_ko", "detail_url"])
    df = pd.read_csv(DATA_FILE).fillna("")
    if 'last_price' in df.columns:
        df['last_price'] = pd.to_numeric(df['last_price'], errors='coerce').fillna(0).astype(int)
    
    # 데이터 마이그레이션: '일반' -> 게임명으로 자동 변환
    if not df.empty and 'sub_category' in df.columns and 'game' in df.columns:
        mask = (df['sub_category'] == '일반')
        df.loc[mask, 'sub_category'] = df.loc[mask, 'game']
        
    return df

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return pd.DataFrame(columns=["date", "card_id", "price"])
    return pd.read_csv(HISTORY_FILE)

def save_data(df):
    df.to_csv(DATA_FILE, index=False, encoding='utf-8-sig')

def get_price_change_info(card_id, current_price):
    history = load_history()
    today = datetime.now().strftime("%Y-%m-%d")
    past = history[(history['card_id'] == card_id) & (history['date'] < today)].sort_values(by="date", ascending=False)
    
    if past.empty: return "-", "#94a3b8"
    last_price = past.iloc[0]['price']
    diff = current_price - last_price
    
    if diff > 0: return f"▲ {diff:,}", "#E11D48"
    elif diff < 0: return f"▼ {abs(diff):,}", "#2563EB"
    else: return "-", "#94a3b8"

# --- 3. SCRAPING ENGINE (High-Value Priority) ---
def get_yuyutei_info(game, card_id):
    url = GAME_URLS.get(game)
    if not url: return None
    try:
        res = crequests.get(url, params={"search_word": card_id}, impersonate="chrome110", timeout=10)
        if res.status_code != 200: return None
        soup = BeautifulSoup(res.content, 'html.parser')
        
        candidates = []
        for b in soup.find_all('div', class_=lambda x: x and 'card-product' in x):
            if card_id.lower() in b.get_text().lower():
                p_tag = b.find('strong', class_=lambda x: x and 'text-end' in x)
                price = 0
                if p_tag:
                    price_match = re.search(r'([0-9,]+)', p_tag.get_text())
                    if price_match:
                        price = int(price_match.group(1).replace(',', ''))
                candidates.append({'box': b, 'price': price})
        
        if not candidates: return None
        
        best_match = sorted(candidates, key=lambda x: x['price'], reverse=True)[0]
        box = best_match['box']
        price = best_match['price']
        
        s_tag = box.find('label', class_=lambda x: x and 'cart_sell_zaiko' in x)
        stock = re.search(r'[:：]\s*(\d+)', s_tag.get_text()).group(1) if s_tag and re.search(r'[:：]\s*(\d+)', s_tag.get_text()) else "×"
        img = box.find('img', class_=lambda x: x and 'img-fluid' in x)
        img_url = img.get('src') if img else ""
        t_ja = img.get('alt', card_id) if img else card_id
        a = box.find('a', href=True)
        d_url = "https://yuyu-tei.jp" + a['href'] if a and not a['href'].startswith('http') else (a['href'] if a else "")
        try: t_ko = translator.translate(t_ja)
        except: t_ko = t_ja
        
        history = load_history()
        today = datetime.now().strftime("%Y-%m-%d")
        existing = history[(history['date'] == today) & (history['card_id'] == card_id)]
        if not existing.empty:
            history.loc[(history['date'] == today) & (history['card_id'] == card_id), 'price'] = price
        else:
            new_record = pd.DataFrame([{"date": today, "card_id": card_id, "price": price}])
            history = pd.concat([history, new_record], ignore_index=True)
        history.to_csv(HISTORY_FILE, index=False, encoding='utf-8-sig')
        
        return {"price": price, "stock": stock, "img": img_url, "t_ja": t_ja, "t_ko": t_ko, "url": d_url}
    except: return None

# --- 4. COMMERCIAL DESIGN SYSTEM ---
st.set_page_config(page_title="TCG 시세동향 Pro", layout="wide")
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;500;600;700;800&display=swap');
        .stApp { background: #FAF9F6 !important; font-family: 'Pretendard', sans-serif; color: #1e293b !important; }
        [data-testid="stSidebar"] { background-color: #F8F7F4 !important; border-right: 1px solid #E2E8F0; }
        
        .stDataFrame, div[data-testid="stTable"] { 
            background: white !important; border-radius: 8px; border: 1px solid #E2E8F0; box-shadow: 0 1px 3px rgba(0,0,0,0.02);
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            background-color: white;
            border: 1px solid #E2E8F0; border-radius: 16px; padding: 0px !important; margin-bottom: 24px;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.025);
            transition: all 0.3s ease; overflow: hidden;
        }
        [data-testid="stVerticalBlockBorderWrapper"]:hover {
            transform: translateY(-5px); box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
            border-color: #B45309;
        }

        .card-title { 
            font-weight: 700; font-size: 0.85rem; color: #0F172A; line-height: 1.4; 
            margin-bottom: 4px; padding: 0 14px;
            display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; height: 58px;
        }
        .card-id { font-size: 0.7rem; color: #94A3B8; font-weight: 500; margin-bottom: 8px; padding: 0 14px; letter-spacing: -0.01em; }
        
        div[data-testid="stPopover"] button {
            width: calc(100% - 28px); margin-left: 14px; margin-right: 14px;
            border: 1px solid #E2E8F0 !important; background-color: #F8FAFC !important;
            color: #0F172A !important; font-weight: 800 !important; font-size: 1.1rem !important;
            padding: 4px 0px !important; border-radius: 8px; line-height: 1.2;
            min-height: auto !important; margin-bottom: 2px !important;
        }
        div[data-testid="stPopover"] button:hover {
            border-color: #B45309 !important; color: #B45309 !important; background-color: #FFF7ED !important;
        }

        .compact-info-row {
            padding: 0 14px; margin-top: 2px; margin-bottom: 8px;
            display: flex; justify-content: space-between; align-items: center;
        }
        .change-indicator { font-size: 0.75rem; font-weight: 700; }
        .stock-tag { 
            font-size: 0.9rem; color: #475569; font-weight: 700; 
            background: #F1F5F9; padding: 3px 10px; border-radius: 6px; 
        }

        .market-row { 
            display: flex; width: 100%; border-top: 1px solid #F1F5F9; background: #FAFAFA; margin-top: 0px;
        }
        .market-btn {
            flex: 1; text-align: center; padding: 10px 0;
            color: #64748B !important; font-size: 0.7rem; font-weight: 600;
            text-decoration: none; border-right: 1px solid #F1F5F9;
            transition: background 0.1s;
        }
        .market-btn:last-child { border-right: none; }
        .market-btn:hover { background: white; color: #B45309 !important; font-weight: 700; }
        
        .section-header {
            background: white; padding: 12px 20px; border-radius: 10px;
            border-left: 5px solid #B45309; box-shadow: 0 2px 4px rgba(0,0,0,0.03);
            margin: 25px 0 15px 0; font-size: 1.1rem; font-weight: 700; color: #1E293B;
            display: flex; align-items: center;
        }
    </style>
""", unsafe_allow_html=True)

df = load_data()

# --- 5. SIDEBAR ---
with st.sidebar:
    st.markdown("<h2 style='color:#B45309; margin-bottom:20px;'>TCG Pro</h2>", unsafe_allow_html=True)
    if 'filter' not in st.session_state: st.session_state.filter = "Dashboard"
    
    def nav_btn(label):
        if st.button(label, use_container_width=True):
            st.session_state.filter = label.replace("◆ ", "").replace("　 ", "")
            st.rerun()

    nav_btn("◆ Dashboard")
    st.markdown("<div style='margin:10px 0; border-top:1px solid #E2E8F0;'></div>", unsafe_allow_html=True)
    for g in GAMES: nav_btn(f"◆ {g}")
    st.markdown("<div style='margin:10px 0; border-top:1px solid #E2E8F0;'></div>", unsafe_allow_html=True)
    for title in WEISS_ORDER: nav_btn(f"　 {title}")

# --- 6. DASHBOARD ---
st.title(f"{st.session_state.filter}")

if st.session_state.filter == "Dashboard":
    movers = []
    if not df.empty:
        for idx, row in df.iterrows():
            ch_str, ch_col = get_price_change_info(row['card_id'], row['last_price'])
            if "▲" in ch_str or "▼" in ch_str:
                movers.append({"Game": row['game'], "Title": row['title_ko'], "Price": f"{row['last_price']:,}", "Change": ch_str})
    
    c_mov, c_up = st.columns([3, 1])
    with c_mov:
        st.markdown('<div class="section-header">⚡ Market Movers (오늘의 변동)</div>', unsafe_allow_html=True)
        if movers:
            st.dataframe(pd.DataFrame(movers), use_container_width=True, hide_index=True)
        else:
            st.info("오늘 변동된 시세 내역이 없습니다.")
    
    with c_up:
        st.markdown('<div class="section-header">Action</div>', unsafe_allow_html=True)
        if st.button("🔄 시세 전체 업데이트", type="primary", use_container_width=True):
            if not df.empty:
                bar = st.progress(0, text="초기화 중..."); log = st.empty()
                total = len(df)
                for i, row in df.iterrows():
                    log.caption(f"[{i+1}/{total}] 업데이트 중: {row['title_ko']}")
                    bar.progress((i+1)/total, text=f"진행률: {int((i+1)/total*100)}%")
                    info = get_yuyutei_info(row['game'], row['card_id'])
                    if info:
                        df.at[i, 'last_price'] = info['price']
                        df.at[i, 'stock'] = info['stock']
                    time.sleep(0.1)
                save_data(df)
                log.success("업데이트 완료!")
                time.sleep(1)
                st.rerun()
            else: st.warning("카드가 없습니다.")

    st.markdown("---")

    st.markdown('<div class="section-header">🗂️ Inventory Management</div>', unsafe_allow_html=True)
    if not df.empty:
        c1, c2 = st.columns([1, 2.5])
        with c1:
            st.caption("카테고리별 요약")
            st.dataframe(df.groupby(['game', 'sub_category']).size().reset_index(name='Count'), use_container_width=True, hide_index=True)
        with c2:
            c_head, c_btn = st.columns([4, 1])
            c_head.caption("전체 리스트 (체크 후 삭제)")
            
            edit_df = df[['sub_category', 'card_id', 'title_ko', 'last_price']].sort_values(by="last_price", ascending=False).copy()
            edit_df.insert(0, "Sel", False)
            
            edited = st.data_editor(
                edit_df, use_container_width=True, hide_index=True,
                column_config={"Sel": st.column_config.CheckboxColumn("✔", width="small"), "last_price": st.column_config.NumberColumn("Price", format="%d 円")},
                disabled=["sub_category", "card_id", "title_ko", "last_price"],
                key="editor"
            )
            
            if st.button("🗑️ 선택 삭제", type="secondary", use_container_width=True):
                del_ids = edited[edited['Sel']]['card_id'].values
                if len(del_ids) > 0:
                    df = df[~df['card_id'].isin(del_ids)]
                    save_data(df)
                    st.rerun()

    with st.expander("➕ 새 카드 등록하기 (진행 상황 표시)", expanded=True):
        c1, c2, c3 = st.columns([3, 1, 1])
        ids_in = c1.text_area("카드 번호 입력", placeholder="S117-010SP\nW132-073SP")
        g_in = c2.selectbox("게임", GAMES)
        
        if g_in == "바이스슈발츠":
            s_in = c3.selectbox("타이틀", WEISS_ORDER)
        else:
            s_in = g_in 
            c3.text_input("타이틀 (자동)", value=s_in, disabled=True)

        if st.button("등록 시작"):
            ids = [x.strip() for x in ids_in.split('\n') if x.strip()][:20]
            if not ids:
                st.warning("카드 ID를 입력해주세요.")
            else:
                progress_bar = st.progress(0, text="준비 중...")
                status_box = st.empty()
                added_count = 0
                for idx, cid in enumerate(ids):
                    status_box.markdown(f"🔍 **분석 중...** (`{cid}`)")
                    progress_bar.progress((idx + 1) / len(ids))
                    info = get_yuyutei_info(g_in, cid)
                    if info and cid not in df['card_id'].values:
                        new_row = {
                            "card_id": cid, "game": g_in, "sub_category": s_in, "last_price": info['price'],
                            "image_url": info['img'], "stock": info['stock'], "title": info['t_ja'],
                            "title_ko": info['t_ko'], "detail_url": info['url']
                        }
                        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                        added_count += 1
                save_data(df)
                status_box.success(f"✅ 작업 완료! {added_count}개의 카드가 추가되었습니다.")
                time.sleep(1.5); st.rerun()

# --- 7. GRID RENDERER ---
def render_grid(target_df):
    target_df = target_df.sort_values(by="last_price", ascending=False)
    hist_db = load_history()
    
    for i in range(0, len(target_df), 6):
        batch = target_df.iloc[i:i+6]
        cols = st.columns(6)
        for j, (idx, row) in enumerate(batch.iterrows()):
            with cols[j]:
                with st.container(border=True):
                    ch_str, ch_col = get_price_change_info(row['card_id'], row['last_price'])
                    ebay_u = f"https://www.ebay.com/sch/i.html?_nkw={quote(row['card_id'] + ' PSA10')}"
                    merc_u = f"https://jp.mercari.com/search?keyword={quote(row['card_id'] + ' PSA10')}"
                    
                    st.markdown(f"""
                        <div style="margin: -15px -15px 12px -15px;">
                            <img src="{row['image_url']}" style="width:100%; display:block; aspect-ratio:1/1.4; object-fit:contain; background:#f8f9fa;">
                        </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown(f"""
                        <div class="card-title" title="{row['title_ko']}">{row['title_ko']}</div>
                        <div class="card-id">{row['card_id']}</div>
                    """, unsafe_allow_html=True)

                    with st.popover(f"{row['last_price']:,} 円", use_container_width=True):
                        st.caption(f"📈 Trend: {row['title_ko']}")
                        c_hist = hist_db[hist_db['card_id'] == row['card_id']].sort_values(by="date")
                        if len(c_hist) > 1:
                            fig = px.line(c_hist, x="date", y="price", markers=True)
                            fig.update_layout(height=200, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
                            st.plotly_chart(fig, use_container_width=True)
                        else: st.info("데이터 수집 중입니다.")

                    st.markdown(f"""
                        <div class="compact-info-row">
                            <span class="change-indicator" style="color:{ch_col};">{ch_str}</span>
                            <span class="stock-tag">Stock: {row['stock']}</span>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown(f"""
                        <div style="margin: 10px -15px -15px -15px;">
                            <div class="market-row">
                                <a href="{row['detail_url']}" target="_blank" class="market-btn">Yuyu</a>
                                <a href="{ebay_u}" target="_blank" class="market-btn">eBay</a>
                                <a href="{merc_u}" target="_blank" class="market-btn">Merc</a>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

f = st.session_state.filter
disp = df.copy()
if f in GAMES: disp = disp[disp['game'] == f]
elif f in WEISS_ORDER: disp = disp[disp['sub_category'] == f]

st.divider()
if not disp.empty:
    if f == "Dashboard":
        all_categories = ["포켓몬", "원피스"] + WEISS_ORDER
        for sub in all_categories:
            s_df = disp[disp['sub_category'] == sub]
            if not s_df.empty:
                st.markdown(f'<div class="section-header">{sub}</div>', unsafe_allow_html=True)
                render_grid(s_df)
                
    elif f == "바이스슈발츠":
        for sub in WEISS_ORDER:
            s_df = disp[disp['sub_category'] == sub]
            if not s_df.empty:
                st.markdown(f'<div class="section-header">{sub}</div>', unsafe_allow_html=True)
                render_grid(s_df)
    else:
        render_grid(disp)
else:
    st.info("데이터가 없습니다. 대시보드에서 카드를 등록해주세요.")