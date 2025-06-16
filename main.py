import streamlit as st
import os
from supabase import create_client, Client
import time


# Konfigurasi aplikasi
MAX_KEYWORDS_PER_USER = 5

# Koneksi ke Supabase
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- FUNGSI OTENTIKASI ---
def sign_in(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state['user'] = res.user
        st.session_state['session'] = res.session
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
            del st.session_state['user']
            st.rerun()

    st.divider()

    # --- Kolom Pengaturan ---
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("1. Pengaturan Profil Anda")
        current_telegram_id = user.user_metadata.get('telegram_user_id', '')
        telegram_id_input = st.text_input(
            "Masukkan Telegram User ID Anda:", 
            value=current_telegram_id, 
            help="Dapatkan ID Anda dari bot @userinfobot di Telegram."
        )
        if st.button("Simpan Telegram ID"):
            try:
                user_id = user.id
                telegram_id = int(telegram_id_input)

                # Simpan atau update ke tabel user_profiles
                supabase.table("user_profiles").upsert({
                    "user_id": user_id,
                    "telegram_user_id": telegram_id
                }).execute()

                st.success("Telegram ID berhasil disimpan!")
                time.sleep(1)
                st.rerun()
            except ValueError:
                st.error("Telegram ID harus berupa angka.")
            except Exception as e:
                st.error(f"Gagal menyimpan ID. Error: {e}")

    with col2:
        st.subheader(f"2. Pilih Keyword (Maks. {MAX_KEYWORDS_PER_USER})")
        
        # Ambil data dari Supabase
        available_keywords_data = supabase.table("available_keywords").select("id, keyword").execute().data
        available_keywords_map = {item['keyword']: item['id'] for item in available_keywords_data}
        
        current_subscriptions_data = supabase.table("subscriptions").select("keyword_id").eq("user_id", user.id).execute().data
        current_subscribed_keyword_ids = {item['keyword_id'] for item in current_subscriptions_data}
        
        id_to_keyword_map = {v: k for k, v in available_keywords_map.items()}
        default_selected_keywords = [id_to_keyword_map[kid] for kid in current_subscribed_keyword_ids]

        # Tampilkan widget multiselect
        selected_keywords = st.multiselect(
            "Pilih stocks yang ingin Anda pantau dari daftar:",
            options=list(available_keywords_map.keys()),
            default=default_selected_keywords
        )

        if st.button("Simpan Perubahan Langganan"):
            if len(selected_keywords) > MAX_KEYWORDS_PER_USER:
                st.error(f"Anda hanya dapat memilih maksimal {MAX_KEYWORDS_PER_USER} keyword.")
            else:
                selected_keyword_ids = {available_keywords_map[kw] for kw in selected_keywords}
                to_add = selected_keyword_ids - current_subscribed_keyword_ids
                to_remove = current_subscribed_keyword_ids - selected_keyword_ids

                try:
                    if to_add:
                        supabase.table("subscriptions").insert([{"user_id": user.id, "keyword_id": kid} for kid in to_add]).execute()
                    if to_remove:
                        supabase.table("subscriptions").delete().in_("keyword_id", list(to_remove)).eq("user_id", user.id).execute()
                    st.success("Perubahan langganan berhasil disimpan!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal menyimpan perubahan: {e}")