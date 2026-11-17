from sqlalchemy import inspect, text
from src.config.database import Base, engine
from src import models
def migrate():
    Base.metadata.create_all(engine)
    # 既有库补列：create_all 不会修改已存在的表
    with engine.begin() as conn:
        existing={c['name'] for c in inspect(conn).get_columns('datasets')}
        additions={
            'spec_id':'INTEGER NULL',
            'lifecycle':"VARCHAR(20) NOT NULL DEFAULT 'current'",
            'parent_id':'INTEGER NULL',
            'raw_records':'JSON NULL',
        }
        for column,ddl in additions.items():
            if column not in existing:
                conn.execute(text(f'ALTER TABLE datasets ADD COLUMN {column} {ddl}'))
if __name__=='__main__':migrate()
