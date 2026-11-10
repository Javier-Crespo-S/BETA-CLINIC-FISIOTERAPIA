import os


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://localhost/beta_clinic_dev",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
