from __future__ import annotations

import os

import bcrypt
import streamlit as st


def authenticated() -> bool:
    return bool(st.session_state.get("authenticated"))


def login() -> bool:
    if authenticated():
        return True
    st.subheader("Thanos login")
    person = st.selectbox("Who is using the app?", ["Brad", "James"])
    password = st.text_input("Shared password", type="password")
    if st.button("Log in"):
        stored = os.getenv("APP_PASSWORD_HASH", "").encode()
        if stored and bcrypt.checkpw(password.encode(), stored):
            st.session_state.authenticated = True
            st.session_state.user = person
            st.rerun()
        st.error("Invalid password")
    return False
