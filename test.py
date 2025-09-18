import psycopg2

from app.config import config

DATABASE_URL = config.postgres_url

VECTOR_DIM = 1536
zero_vec = ",".join(["0"] * VECTOR_DIM)
vec_literal = f"'[{zero_vec}]'::vector"

sql = f"""
INSERT INTO docs (slug, title, content, metadata, embedding)
VALUES ('py-doc-1','blog/py-test.md', 'Python test content', '{{"title":"py test"}}'::jsonb, {vec_literal})
RETURNING id;
"""

with psycopg2.connect(DATABASE_URL) as conn:
    with conn.cursor() as cur:
        cur.execute(sql)
        inserted_id = cur.fetchone()[0]
        print("Inserted id:", inserted_id)