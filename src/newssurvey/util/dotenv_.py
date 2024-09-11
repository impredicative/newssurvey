import dotenv


def load_dotenv():
    """Load the .env file normally and also from the current directory."""
    dotenv.load_dotenv()
    dotenv.load_dotenv(dotenv.find_dotenv(usecwd=True))
