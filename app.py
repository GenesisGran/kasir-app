import streamlit as st
import httpx
import pandas as pd
from datetime import datetime, date, timedelta, timezone
import json

# --- 1. CONFIG & STYLES ---
st.set_page_config(page_title="Toko Minuman Sumber Jaya", layout="wide")

st.markdown("""
    <style>
    /* Menghilangkan ikon link (anchor) di samping header/judul */
    .viewerBadge_container__1QSob, .st-emotion-cache-15zrgzn {
        display: none !important;
    }
    a.header-anchor {
        display: none !important;
    }

    /* Menempatkan konten di tengah layar */
    [data-testid="stAppViewContainer"] { 
        background-color: #0F172A;
    }
    
    [data-testid="stVerticalBlock"] > div:first-child {
        margin-top: auto;
        margin-bottom: auto;
    }

    html, body, [class*="css"], .stMarkdown { color: #F8FAFC !important; }
   
    .stTextInput input {
        background-color: #1E293B !important;
        color: white !important;
        border: 2px solid #334155 !important;
        border-radius: 12px !important;
        text-align: center !important;
    }
   
    .stButton>button {
        border: 2px solid #3B82F6 !important;
        border-radius: 12px !important;
        background-color: transparent !important;
        color: white !important;
        width: 100%;
        height: 50px;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        background-color: #1E293B !important;
        transform: scale(1.02);
    }

    .p-card {
        padding: 12px;
        border-radius: 10px;
        border: 1px solid #334155;
        margin-bottom: 8px;
    }
    .stok-aman { background-color: #1E293B; border-left: 5px solid #10B981; }
    .stok-kritis { background-color: #451a1a; border-left: 5px solid #EF4444; }
   
    .nota-lunas { background-color: #064e3b; border: 1px solid #10B981; border-radius: 10px; padding: 10px; margin-bottom: 5px; }
    .nota-belum-lunas { background-color: #7f1d1d; border: 1px solid #EF4444; border-radius: 10px; padding: 10px; margin-bottom: 5px; }

    .cart-btn button {
        border: 2px solid #3B82F6 !important;
        height: 45px !important;
        width: 100% !important;
        font-size: 20px !important;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .btn-delete button {
        border: 2px solid #EF4444 !important;
        color: #EF4444 !important;
        background-color: rgba(239, 68, 68, 0.1) !important;
    }

    [data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
    }

    @media print {
        .no-print { display: none !important; }
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATABASE CONNECTION ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

def call_db(endpoint: str, method="GET", data=None, params=None):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Accept-Profile": "toko",
        "Content-Profile": "toko",
        "Prefer": "return=representation" if method in ["POST", "PATCH"] else ""
    }
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    try:
        with httpx.Client(timeout=15.0, verify=False) as client:
            if method == "GET": resp = client.get(url, headers=headers, params=params)
            elif method == "POST": resp = client.post(url, headers=headers, json=data)
            elif method == "PATCH": resp = client.patch(url, headers=headers, json=data)
           
            if resp.status_code in [200, 201]: return resp.json()
            elif resp.status_code == 204: return True
            return None
    except Exception as e:
        st.error(f"Koneksi Database Gagal: {e}")
        return None

@st.cache_data(ttl=300)
def get_cached_products():
    return call_db("produk?select=*&order=nama_produk")

# Fungsi Waktu Konsisten ke WIB
def get_now_wib():
    return datetime.now(timezone(timedelta(hours=7)))

def format_waktu(waktu_str):
    if not waktu_str: return "-"
    try:
        # Menghapus info timezone dari string jika ada agar tidak konflik saat parsing
        clean_str = waktu_str.split('+')[0].split('.')[0].replace("Z", "")
        dt = datetime.fromisoformat(clean_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return waktu_str[:19]

def format_rupiah_compact(val):
    if val >= 1_000_000:
        return f"Rp {val/1_000_000:.2f} Jt"
    elif val >= 1_000:
        return f"Rp {val/1_000:.1f} Rb"
    return f"Rp {val:,.0f}"

# --- 3. SESSION STATE ---
if 'cart' not in st.session_state: st.session_state.cart = {}
if 'page' not in st.session_state: st.session_state.page = "🛒 Kasir"

# --- 4. SIDEBAR ---
with st.sidebar:
    st.markdown("<div class='no-print'>", unsafe_allow_html=True)
    st.title("🥤 Sumber Jaya")
    st.session_state.page = st.radio("Menu", ["🛒 Kasir", "📦 Inventori & Tambah Stok", "🧾 Nota Penjualan", "📈 Laporan Keuangan"])
    st.markdown("</div>", unsafe_allow_html=True)

# --- 5. HALAMAN KASIR ---
if st.session_state.page == "🛒 Kasir":
    st.header("🛒 Kasir")
    price_mode = st.radio("Mode Harga:", ["Jualan (Toko) 🏪", "Rumah (Ecer) 🏠"], horizontal=True)

    col1, col2 = st.columns([1.8, 1.2])
   
    with col1:
        search = st.text_input("", placeholder="🔍 Cari nama minuman...")
        prods = get_cached_products()
       
        if prods:
            filtered = [p for p in prods if search.lower() in p['nama_produk'].lower()] if search else prods
            for p in filtered:
                stok = p.get('stok') or 0
                card_class = "stok-kritis" if stok < 50 else "stok-aman"
                h_rumah = float(p.get('harga_jual_retail') or 0)
                h_jualan = float(p.get('harga_jual_grosir') or 0)
                
                is_jualan = "Jualan" in price_mode and h_jualan > 0
                harga_final = h_jualan if is_jualan else h_rumah
                label_harga = "Harga Jualan" if is_jualan else "Harga Rumah"
               
                st.markdown(f"""<div class="p-card {card_class}"><b>{p['nama_produk']}</b> ({p['satuan']})<br>Stok: {stok} | Rp {harga_final:,.0f} ({label_harga})</div>""", unsafe_allow_html=True)
                if st.button(f"Tambah Ke Keranjang", key=f"add_{p['id']}"):
                    pid = str(p['id'])
                    if pid in st.session_state.cart: st.session_state.cart[pid]['qty'] += 1
                    else: st.session_state.cart[pid] = {
                        "id": p['id'], 
                        "nama": p['nama_produk'], 
                        "harga": harga_final, 
                        "modal": float(p.get('harga_modal') or 0), 
                        "qty": 1,
                        "tipe": label_harga
                    }
                    st.rerun()

    with col2:
        st.subheader("🧺 Keranjang")
        total_h, total_m = 0, 0
        for pid, itm in list(st.session_state.cart.items()):
            with st.container(border=True):
                st.markdown(f"**{itm['nama']}**")
                st.caption(f"{itm['tipe']} @ Rp {itm['harga']:,.0f}")
                
                q1, q2, q3, q4 = st.columns([1, 1, 1, 1.2])
                with q1:
                    st.markdown('<div class="cart-btn">', unsafe_allow_html=True)
                    if st.button("➖", key=f"min_{pid}"):
                        if st.session_state.cart[pid]['qty'] > 1: st.session_state.cart[pid]['qty'] -= 1
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
                
                q2.markdown(f"<h3 style='text-align:center; margin:0;'>{itm['qty']}</h3>", unsafe_allow_html=True)
                
                with q3:
                    st.markdown('<div class="cart-btn">', unsafe_allow_html=True)
                    if st.button("➕", key=f"pls_{pid}"):
                        st.session_state.cart[pid]['qty'] += 1
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
                
                with q4:
                    st.markdown('<div class="cart-btn btn-delete">', unsafe_allow_html=True)
                    if st.button("✕", key=f"del_{pid}"):
                        del st.session_state.cart[pid]
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
                
                total_h += itm['harga'] * itm['qty']
                total_m += itm['modal'] * itm['qty']

        st.divider()
        st.write(f"### Total: Rp {total_h:,.0f}")
        catatan = st.text_input("📝 Catatan", placeholder="Nama pelanggan...")
        status_bayar = st.radio("Status Pembayaran:", ["Lunas", "Belum Lunas"], index=1, horizontal=True)
       
        if st.button(f"💾 SIMPAN NOTA ({status_bayar.upper()})", use_container_width=True):
            if st.session_state.cart:
                with st.spinner("Menyimpan..."):
                    now_wib = get_now_wib().isoformat()
                    tx = {
                        "total_harga": total_h, 
                        "total_modal": total_m, 
                        "keuntungan_bersih": total_h - total_m, 
                        "status_pembayaran": status_bayar, 
                        "catatan": catatan, 
                        "waktu_pelunasan": now_wib if status_bayar == "Lunas" else None,
                        "waktu_transaksi": now_wib # Paksa waktu transaksi pakai WIB
                    }
                    res_p = call_db("penjualan", "POST", tx)
                    if res_p:
                        penj_id = res_p[0]['id']
                        for pid, itm in st.session_state.cart.items():
                            call_db("item_penjualan", "POST", {"penjualan_id": penj_id, "produk_id": int(pid), "jumlah": itm['qty'], "subtotal_harga": itm['harga'] * itm['qty'], "subtotal_modal": itm['modal'] * itm['qty']})
                            p_curr = call_db(f"produk?id=eq.{pid}&select=stok")
                            if p_curr: call_db(f"produk?id=eq.{pid}", "PATCH", {"stok": (p_curr[0]['stok'] or 0) - itm['qty']})
                        st.session_state.cart = {}
                        st.cache_data.clear()
                        st.success("Nota Tersimpan!")
                        st.rerun()

# --- 6. INVENTORI & TAMBAH STOK ---
elif st.session_state.page == "📦 Inventori & Tambah Stok":
    st.header("📦 Daftar Stok Barang")
    inv = call_db("produk?select=*&order=nama_produk")
    if inv:
        df = pd.DataFrame(inv)
        df_display = df[["nama_produk", "stok", "satuan", "harga_modal", "harga_jual_retail", "harga_jual_grosir"]].copy()
        df_display.columns = ["Nama Barang", "Sisa Stok", "Satuan", "Harga Modal", "Harga Rumah (Ecer)", "Harga Jualan"]
        st.dataframe(df_display, use_container_width=True)
        
        st.subheader("➕ Tambah Stok Manual")
        search_stok = st.text_input("🔍 Cari produk...", placeholder="Contoh: Aqua")
        options_df = df[df['nama_produk'].str.contains(search_stok, case=False)] if search_stok else df
        if not options_df.empty:
            sel_p_name = st.selectbox("Pilih Produk:", options_df['nama_produk'].tolist())
            qty_add = st.number_input("Jumlah Stok Masuk", min_value=1, value=1)
            if st.button("Update Stok Sekarang"):
                p_row = df[df['nama_produk'] == sel_p_name].iloc[0]
                if call_db(f"produk?id=eq.{p_row['id']}", "PATCH", {"stok": int((p_row['stok'] or 0) + qty_add)}):
                    st.cache_data.clear()
                    st.success(f"Stok {sel_p_name} berhasil diperbarui!")
                    st.rerun()

# --- 7. NOTA PENJUALAN ---
elif st.session_state.page == "🧾 Nota Penjualan":
    st.header("🧾 Riwayat Penjualan")
    c1, c2, c3, c4 = st.columns([1.5, 1.5, 1.5, 2])
    f_start = c1.date_input("Dari", date.today() - timedelta(days=7))
    f_end = c2.date_input("Sampai", date.today())
    f_status = c3.selectbox("Status", ["Semua", "Lunas", "Belum Lunas"])
    f_search = c4.text_input("🔍 Cari Catatan/Pelanggan", placeholder="Ketik nama...")

    query = f"penjualan?select=*&waktu_transaksi=gte.{f_start.isoformat()}&waktu_transaksi=lte.{f_end.isoformat()}T23:59:59&order=waktu_transaksi.desc"
    if f_status != "Semua": query += f"&status_pembayaran=eq.{f_status}"
    if f_search: query += f"&catatan=ilike.*{f_search}*"
       
    notas = call_db(query)
    if notas:
        for n in notas:
            bg = "nota-lunas" if n['status_pembayaran'] == "Lunas" else "nota-belum-lunas"
            st.markdown(f"<div class='{bg}'>", unsafe_allow_html=True)
            waktu_t = format_waktu(n['waktu_transaksi'])
            waktu_l = format_waktu(n['waktu_pelunasan'])
            
            with st.expander(f"Nota #{n['id']} - {n['catatan'] or 'Pembeli'} | Rp {float(n['total_harga']):,.0f}"):
                st.write(f"📅 **Waktu Transaksi:** {waktu_t}")
                st.write(f"✅ **Waktu Lunas:** {waktu_l}")
                
                item_query = f"item_penjualan?penjualan_id=eq.{n['id']}&select=*,produk(nama_produk)"
                items_data = call_db(item_query)
                item_rows_html = ""
                if items_data:
                    for i in items_data:
                        nama = i['produk']['nama_produk']
                        qty = i['jumlah']; sub = float(i['subtotal_harga'])
                        st.write(f"🔹 **{nama}** x{qty} — Rp {sub:,.0f}")
                        item_rows_html += f"<tr><td>{nama}</td><td style='text-align:center'>{qty}</td><td style='text-align:right'>Rp {sub:,.0f}</td></tr>"
               
                c_n1, c_n2 = st.columns(2)
                if n['status_pembayaran'] == "Belum Lunas":
                    if c_n1.button("✅ LUNASKAN", key=f"pay_{n['id']}"):
                        now_wib = get_now_wib().isoformat()
                        call_db(f"penjualan?id=eq.{n['id']}", "PATCH", {"status_pembayaran": "Lunas", "waktu_pelunasan": now_wib})
                        st.rerun()
                if c_n2.button("🖨️ PRINT NOTA", key=f"prnt_{n['id']}"):
                    p_html = f"""<div style="font-family:monospace; width:280px; color:black; background:white; padding:10px; border:1px solid #ccc;"><center><b style="font-size:16px;">Toko Minuman Sumber Jaya</b><br>Nota: #{n['id']}</center><hr style="border-top:1px dashed black;"><small>Tgl: {waktu_t}<br>Catatan: {n['catatan'] or '-'}</small><hr style="border-top:1px dashed black;"><table style="width: 100%; font-size:12px;">{item_rows_html}</table><hr style="border-top:1px dashed black;"><table style="width:100%; font-size:13px;"><tr><td><b>TOTAL</b></td><td style="text-align:right"><b>Rp {float(n['total_harga']):,.0f}</b></td></tr></table><hr style="border-top:1px dashed black;"><center><small>Terima Kasih</small></center></div><script>window.print();</script>"""
                    st.components.v1.html(p_html, height=450)
            st.markdown("</div>", unsafe_allow_html=True)

# --- 8. LAPORAN KEUANGAN ---
elif st.session_state.page == "📈 Laporan Keuangan":
    st.header("📈 Analisis Keuangan & Penjualan")
   
    lc1, lc2 = st.columns(2)
    l_start = lc1.date_input("Mulai Laporan", date.today().replace(day=1))
    l_end = lc2.date_input("Akhir Laporan", date.today())
   
    l_query = f"penjualan?select=*&waktu_transaksi=gte.{l_start.isoformat()}&waktu_transaksi=lte.{l_end.isoformat()}T23:59:59"
    data = call_db(l_query)
   
    if data:
        df = pd.DataFrame(data)
        for col in ['total_harga', 'total_modal', 'keuntungan_bersih']:
            df[col] = df[col].astype(float)
        
        df['waktu_transaksi'] = df['waktu_transaksi'].apply(format_waktu)
       
        lunas_df = df[df['status_pembayaran'] == "Lunas"]
        piutang_df = df[df['status_pembayaran'] == "Belum Lunas"]
       
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Omzet Lunas", format_rupiah_compact(lunas_df['total_harga'].sum()))
        m2.metric("Laba Bersih", format_rupiah_compact(lunas_df['keuntungan_bersih'].sum()), delta=f"{len(lunas_df)} Trx")
        m3.metric("Piutang", format_rupiah_compact(piutang_df['total_harga'].sum()), delta=f"{len(piutang_df)} Nota", delta_color="inverse")
        m4.metric("Modal Terputar", format_rupiah_compact(df['total_modal'].sum()))
       
        st.divider()
       
        tab_list, tab_prod = st.tabs(["📄 Daftar Transaksi", "🍹 Produk Terlaris"])
       
        with tab_list:
            st.dataframe(df[['waktu_transaksi', 'catatan', 'total_harga', 'status_pembayaran']].sort_values('waktu_transaksi', ascending=False), use_container_width=True)
           
        with tab_prod:
            prod_query = f"barang_terjual?select=nama_produk,jumlah&waktu_transaksi=gte.{l_start.isoformat()}&waktu_transaksi=lte.{l_end.isoformat()}T23:59:59"
            bt_data = call_db(prod_query)
           
            if bt_data:
                pdf = pd.DataFrame(bt_data)
                top_p = pdf.groupby('nama_produk')['jumlah'].sum().sort_values(ascending=False).head(10)
               
                if not top_p.empty:
                    st.subheader("10 Produk Paling Laris (Qty)")
                    st.bar_chart(top_p)
                    st.table(top_p.reset_index().rename(columns={'nama_produk': 'Nama Produk', 'jumlah': 'Total Terjual'}))
                else:
                    st.info("Belum ada data barang terjual pada periode ini.")
            else:
                st.warning("Data rincian produk tidak ditemukan.")
    else:
        st.info("Tidak ada transaksi pada periode ini.")