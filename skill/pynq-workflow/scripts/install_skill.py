"""Copy the portable package to an explicitly chosen agent skill directory."""
from pathlib import Path
import argparse,shutil,sys

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--destination',required=True,help='New directory for the installed pynq-workflow skill')
    args=p.parse_args();source=Path(__file__).resolve().parents[1];dest=Path(args.destination).expanduser().resolve()
    if dest.exists():p.error('Destination exists; choose a new directory. No existing skills are overwritten.')
    if source==dest or source in dest.parents or dest in source.parents:p.error('Installation directory must be separate from the source package')
    shutil.copytree(source,dest,ignore=shutil.ignore_patterns('__pycache__'))
    entry=dest/'skill.md'
    if entry.exists():entry.rename(dest/'SKILL.md')
    if not (dest/'SKILL.md').is_file():raise RuntimeError('Missing skill entrypoint')
    print(str(dest/'SKILL.md'));return 0

if __name__=='__main__':sys.exit(main())
