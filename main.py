import flet as ft
from ui.app import main as app_main
from utils.logger import logger
from utils.paths import configure_macos_flet_client

if __name__ == "__main__":
    logger.info("Starting SonicForge Application")
    configure_macos_flet_client()
    ft.run(app_main)
