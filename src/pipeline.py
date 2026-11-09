"""Command-line entry point.

    python -m src.pipeline all          # ingest everything + transform
    python -m src.pipeline swissgrid    # only Swissgrid files
    python -m src.pipeline meteo        # only MeteoSwiss download/load
    python -m src.pipeline transform    # only dbt models, tests, exports
"""
import argparse
import logging
import sys
import time

from src import ingest_meteoswiss, ingest_swissgrid, transform
from src.db import connect


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Swiss energy x weather pipeline")
    parser.add_argument("step", choices=["all", "swissgrid", "meteo", "transform"])
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    t0 = time.time()

    # 1. Extract + load (Python)
    if args.step in ("all", "swissgrid", "meteo"):
        con = connect()
        try:
            if args.step in ("all", "swissgrid"):
                ingest_swissgrid.run(con)
            if args.step in ("all", "meteo"):
                ingest_meteoswiss.run(con)
        finally:
            con.close()

    # 2. Transform + test (dbt) and export
    if args.step in ("all", "transform"):
        try:
            transform.run()
        except transform.DataTestError as e:
            logging.error(str(e))
            return 1

    logging.info("done in %.1fs", time.time() - t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
