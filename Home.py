import streamlit as st
import os
from supabase import create_client, Client
import time





# Koneksi ke Supabase
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Ambil highest unlocked milestone
milestones = supabase.table("community_unlocks").select("*").eq("unlocked", True).order("max_keywords_allowed", desc=True).execute().data
if milestones:
    MAX_KEYWORDS_PER_USER = milestones[0]['max_keywords_allowed']
else:
    MAX_KEYWORDS_PER_USER = 5  # fallback default

# --- FUNGSI CACHING ---
@st.cache_data(ttl=300)  # Cache selama 5 menit
def get_available_keywords():
    """Mengambil daftar keyword yang tersedia dengan caching"""
    try:
        response = supabase.table("available_keywords").select("id, keyword").execute()
        return {item['keyword']: item['id'] for item in response.data}
    except Exception as e:
        st.error(f"Error mengambil keywords: {e}")
        return {}

@st.cache_data(ttl=60)  # Cache selama 1 menit untuk data yang lebih dinamis
def get_user_subscriptions(user_id):
    """Mengambil langganan user dengan caching"""
    try:
        response = supabase.table("subscriptions").select("keyword_id").eq("user_id", user_id).execute()
        return {item['keyword_id'] for item in response.data}
    except Exception as e:
        st.error(f"Error mengambil subscriptions: {e}")
        return set()

@st.cache_data(ttl=300)  # Cache selama 5 menit
def get_user_telegram_id(user_id):
    """Mengambil Telegram ID user dari database dengan caching"""
    try:
        response = supabase.table("user_profiles").select("telegram_user_id").eq("user_id", user_id).execute()
        if response.data:
            return str(response.data[0]['telegram_user_id']) if response.data[0]['telegram_user_id'] else ''
        return ''
    except Exception as e:
        st.error(f"Error mengambil Telegram ID: {e}")
        return ''

# --- FUNGSI UNTUK CLEAR CACHE ---
def clear_user_cache(user_id):
    """Clear cache untuk user tertentu"""
    get_user_subscriptions.clear()
    get_user_telegram_id.clear()
    # Bisa juga clear specific cache jika diperlukan

def clear_all_cache():
    """Clear semua cache"""
    get_available_keywords.clear()
    get_user_subscriptions.clear()
    get_user_telegram_id.clear()

# --- FUNGSI OTENTIKASI ---
def sign_in(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state['user'] = res.user
        st.session_state['session'] = res.session
        # Clear cache untuk user baru
        clear_user_cache(res.user.id)
        st.rerun()
    except Exception as e:
        st.error(f"Gagal login: {e}")

# --- HALAMAN UTAMA APLIKASI ---
st.set_page_config(page_title="GaG Stocks Monitoring", layout="wide")
st.title("📢 Layanan Notifikasi Stocks Grow a Garden")

# Jika user belum login
if 'user' not in st.session_state:
    st.info("Silakan login atau register untuk mengelola notifikasi stocks favorit Anda.")
    login_tab, register_tab = st.tabs(["Login", "Register"])
    
    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                sign_in(email, password)
    
    with register_tab:
        with st.form("register_form"):
            email = st.text_input("Email", key="reg_email")
            password = st.text_input("Password", type="password", key="reg_password")
            if st.form_submit_button("Register"):
                try:
                    supabase.auth.sign_up({"email": email, "password": password})
                    st.success("Registrasi berhasil! Cek email untuk verifikasi, lalu login.")
                except Exception as e:
                    st.error(f"Gagal register: {e}")
else:
    # --- JIKA USER SUDAH LOGIN ---
    user = st.session_state.user
    
    col_header, col_logout = st.columns([4, 1])
    with col_header:
        st.header(f"Selamat Datang, {user.email.split('@')[0]}!")
    with col_logout:
        if st.button("Logout"):
            supabase.auth.sign_out()
            # Clear cache saat logout
            clear_user_cache(user.id)
            del st.session_state['user']
            if 'session' in st.session_state:
                del st.session_state['session']
            st.rerun()

    st.divider()

    # --- Kolom Pengaturan ---
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("1. Pengaturan Profil Anda")
        
        # Ambil Telegram ID dari database menggunakan cache
        current_telegram_id = get_user_telegram_id(user.id)
        
        telegram_id_input = st.text_input(
            "Masukkan Telegram User ID Anda:", 
            value=current_telegram_id, 
            help="Dapatkan ID Anda dari bot @userinfobot di Telegram."
        )
        
        col_save, col_refresh = st.columns([2, 1])
        with col_save:
            if st.button("Simpan Telegram ID"):
                try:
                    user_id = user.id
                    telegram_id = int(telegram_id_input)

                    # Simpan atau update ke tabel user_profiles
                    supabase.table("user_profiles").upsert({
                        "user_id": user_id,
                        "telegram_user_id": telegram_id
                    }).execute()

                    # Clear cache setelah update
                    get_user_telegram_id.clear()
                    
                    st.success("Telegram ID berhasil disimpan!")
                    time.sleep(1)
                    st.rerun()
                except ValueError:
                    st.error("Telegram ID harus berupa angka.")
                except Exception as e:
                    st.error(f"Gagal menyimpan ID. Error: {e}")
        
        with col_refresh:
            if st.button("🔄 Refresh"):
                get_user_telegram_id.clear()
                st.rerun()

    with col2:
        st.subheader(f"2. Pilih Keyword (Maks. {MAX_KEYWORDS_PER_USER})")
        
        # Ambil data menggunakan fungsi cache
        available_keywords_map = get_available_keywords()
        current_subscribed_keyword_ids = get_user_subscriptions(user.id)
        
        # Mapping untuk mendapatkan keyword dari ID
        id_to_keyword_map = {v: k for k, v in available_keywords_map.items()}
        default_selected_keywords = [id_to_keyword_map[kid] for kid in current_subscribed_keyword_ids if kid in id_to_keyword_map]

        # Tampilkan widget multiselect
        selected_keywords = st.multiselect(
            "Pilih stocks yang ingin Anda pantau dari daftar:",
            options=list(available_keywords_map.keys()),
            default=default_selected_keywords
        )

        col_save_sub, col_refresh_sub = st.columns([2, 1])
        with col_save_sub:
            if st.button("Simpan Perubahan Langganan"):
                if len(selected_keywords) > MAX_KEYWORDS_PER_USER:
                    st.error(f"Anda hanya dapat memilih maksimal {MAX_KEYWORDS_PER_USER} keyword.")
                else:
                    selected_keyword_ids = {available_keywords_map[kw] for kw in selected_keywords}
                    to_add = selected_keyword_ids - current_subscribed_keyword_ids
                    to_remove = current_subscribed_keyword_ids - selected_keyword_ids

                    try:
                        if to_add:
                            supabase.table("subscriptions").insert([
                                {"user_id": user.id, "keyword_id": kid} for kid in to_add
                            ]).execute()
                        if to_remove:
                            supabase.table("subscriptions").delete().in_(
                                "keyword_id", list(to_remove)
                            ).eq("user_id", user.id).execute()
                        
                        # Clear cache setelah update
                        get_user_subscriptions.clear()
                        
                        st.success("Perubahan langganan berhasil disimpan!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal menyimpan perubahan: {e}")
        
        with col_refresh_sub:
            if st.button("🔄 Refresh", key="refresh_subscriptions"):
                get_user_subscriptions.clear()
                get_available_keywords.clear()
                st.rerun()

    # --- SECTION TAMBAHAN: INFO CACHE DAN DEBUG ---
    if st.checkbox("Tampilkan Info", key="debug_mode"):
        st.divider()
        st.subheader("Additional Information")
        
        col_debug1, col_debug2 = st.columns(2)
        
        with col_debug1:
            st.write("**Cache Status:**")
            st.write(f"- Available Keywords: {len(get_available_keywords())} items")
            st.write(f"- User Subscriptions: {len(get_user_subscriptions(user.id))} items")
            st.write(f"- Current Telegram ID: '{get_user_telegram_id(user.id)}'")
        
        with col_debug2:
            if st.button("🗑️ Clear All Cache"):
                clear_all_cache()
                st.success("Semua cache telah dibersihkan!")
                time.sleep(1)
                st.rerun()
        
        # Display current subscriptions
        if current_subscribed_keyword_ids:
            st.write("**Current Subscribed Keywords:**")
            subscribed_keywords = [id_to_keyword_map.get(kid, f"Unknown ID: {kid}") for kid in current_subscribed_keyword_ids]
            st.write(", ".join(subscribed_keywords))