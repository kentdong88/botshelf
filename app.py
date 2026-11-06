"""BotShelf entrypoint; keep the earlier WANDS research lab available."""
import runpy
from pathlib import Path
import streamlit as st

st.set_page_config(page_title="BotShelf | Agent-ready shelf",page_icon="◈",layout="wide")
workspace=st.sidebar.selectbox("Product workspace",["Amazon shelf lab","WANDS research lab"],key="product_workspace")
if workspace=="Amazon shelf lab":
    from botshelf.shelf_ui import main
    main()
else:
    runpy.run_path(str(Path(__file__).with_name("legacy_app.py")),run_name="__main__")
