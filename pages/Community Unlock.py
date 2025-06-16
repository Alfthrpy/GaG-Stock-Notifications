import streamlit as st
from supabase import create_client, Client
import os

# Supabase connection
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Konfigurasi
TARGET_ACTIVE_USERS = 10
APP_LINK = "https://gag-stock-monitor.streamlit.app"  # Ganti sesuai URL kamu

# Halaman
st.set_page_config(page_title="Community Unlock 🚀", layout="centered")
st.title("🎯 Community Unlock: Buka Fitur Tambahan Bersama!")

st.markdown("""
Aplikasi ini saat ini hanya membolehkan **maksimal 5 keyword item** untuk dimonitor per pengguna.
**kalau kita berhasil mengumpulkan 10 pengguna aktif**, maka sistem akan membuka fitur untuk memantau lebih banyak item. Gacor lek!
""")

# Ambil user aktif
subscriptions = supabase.table("subscriptions").select("user_id").execute()
active_users = len(set(row['user_id'] for row in subscriptions.data))

# Ambil semua milestone unlock
milestones = supabase.table("community_unlocks").select("*").order("target_user_count", desc=False).execute().data

st.title("Campaign Unlock Progress")

for milestone in milestones:
    target = milestone['target_user_count']
    keyword_limit = milestone['max_keywords_allowed']
    unlocked = active_users >= target

    st.subheader(f"🎁 Unlock {keyword_limit} Keywords (Butuh {target} user aktif)")
    progress = min(active_users / target, 1.0)
    st.progress(progress)
    st.markdown(f"👥 {active_users} / {target} user aktif")

    if unlocked:
        st.success("✅ Terbuka!")
    else:
        st.warning("⏳ Belum tercapai.")

# Copy link
st.markdown("---")
st.markdown("📲 **Bagikan aplikasi ini ke temanmu:**")
st.code(APP_LINK, language='text')

st.caption("Setiap pengguna yang mendaftar dan menambahkan keyword akan dihitung sebagai user aktif. Ayo share ke temen temen Grow a Garden kamu!")
