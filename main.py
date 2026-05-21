import flet as ft
from ui.app import main as app_main
from utils.logger import logger

if __name__ == "__main__":
    logger.info("Starting SonicForge Application")
    ft.run(app_main)
