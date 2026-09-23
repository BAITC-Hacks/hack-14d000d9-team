"""Read-only catalog import; credentials come only from environment/.env."""
import argparse
import json
from dotenv import load_dotenv
from backend.catalog import Catalog, CatalogError, ROOT

if __name__=='__main__':
    load_dotenv(ROOT/'.env')
    parser=argparse.ArgumentParser()
    parser.add_argument('--pages',type=int,default=2)
    parser.add_argument('--force',action='store_true')
    args=parser.parse_args()
    if not 1<=args.pages<=500: parser.error('pages must be 1..500')
    try: print(json.dumps(Catalog().import_pages(args.pages,force=args.force),ensure_ascii=False,indent=2))
    except CatalogError as e: raise SystemExit(str(e)) from None
