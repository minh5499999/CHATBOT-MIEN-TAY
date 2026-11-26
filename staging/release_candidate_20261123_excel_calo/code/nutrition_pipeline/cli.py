import argparse,json
from pathlib import Path
from .intake import import_draft,write_new
from .review import ReviewQueue

def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
    imp=sub.add_parser('import');imp.add_argument('filename');imp.add_argument('output_name')
    review=sub.add_parser('review');review.add_argument('decision_file')
    sub.add_parser('status');args=parser.parse_args()
    build=Path(__file__).resolve().parents[2];root=build/'pipeline'
    if args.command=='status':
        events=ReviewQueue(root).events();print(json.dumps(dict(review_actions=len(events),registry=json.loads((build/'nutrition_data/approval_registry.json').read_text()),source_verified_by_tool=False)));return
    if (build/'REVIEW_FROZEN.json').exists():raise RuntimeError('Frozen candidate: use a disposable copy/new version; never change this release')
    if args.command=='import':
        if Path(args.filename).name!=args.filename or Path(args.output_name).name!=args.output_name:raise ValueError('Use basenames only')
        incoming=build/'nutrition_sources/incoming'
        result=import_draft(incoming/args.filename,incoming,build/'nutrition_sources/review_queue',root/'bundles'/args.output_name)
    else:
        if Path(args.decision_file).name!=args.decision_file:raise ValueError('Use a decision basename')
        decision=json.loads((root/'decisions'/args.decision_file).read_text(encoding='utf-8'))
        result=ReviewQueue(root).record(decision)
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
