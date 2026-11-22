"""Isolated read-only Neo4j health check; never print credentials."""
import json
import os
from pathlib import Path


def main():
    try:
        from dotenv import dotenv_values
        settings = dotenv_values(Path(__file__).resolve().parents[1] / '.env')
        for key in ('NEO4J_URI', 'NEO4J_USER', 'NEO4J_PASSWORD', 'NEO4J_DATABASE'):
            if settings.get(key) is not None:
                os.environ[key] = settings[key]
        if not os.environ.get('NEO4J_PASSWORD'):
            print(json.dumps({'ok': False, 'error': 'Thiếu NEO4J_PASSWORD trong cấu hình.'}))
            return
        from neo4j import GraphDatabase
        with GraphDatabase.driver(os.environ.get('NEO4J_URI', 'bolt://localhost:7687'),
                                  auth=(os.environ.get('NEO4J_USER', 'neo4j'), os.environ['NEO4J_PASSWORD']),
                                  connection_timeout=4, connection_acquisition_timeout=4,
                                  max_transaction_retry_time=0) as driver:
            result = driver.execute_query('RETURN 1 AS ok', database_=os.environ.get('NEO4J_DATABASE', 'neo4j'))
            print(json.dumps({'ok': result.records[0]['ok'] == 1}))
    except Exception as error:
        print(json.dumps({'ok': False, 'error': getattr(error, 'code', type(error).__name__)}))


if __name__ == '__main__':
    main()
