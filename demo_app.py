"""Démo autonome des deux nouveaux onglets CWP :  streamlit run demo_app.py"""
import streamlit as st

from tab_glossaire_fraudes import render_glossaire_fraudes
from tab_regulatory_flash import render_regulatory_flash

st.set_page_config(page_title="CWP – Compliance Watch Platform", page_icon="🛡️", layout="wide")
st.title("CWP – Compliance Watch Platform")

tab_flash, tab_glossaire = st.tabs(["📌 Regulatory Flash", "📚 Glossaire des fraudes"])
with tab_flash:
    render_regulatory_flash()
with tab_glossaire:
    render_glossaire_fraudes()
