from src.engine import build_engine
from src.scene_play import run_game


def main():
    engine = build_engine()
    run_game(engine)


if __name__ == "__main__":
    main()
