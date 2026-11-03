"""withlib.py script.py args... : run a script with extra packages (scipy, shapely for maze2b.py) on sys.path.
The packages live in $PYLIB (default ../pylib next to this file), installed with: python -m pip install --target DIR scipy shapely"""
import sys, os, runpy
sys.path.insert(0, os.environ.get('PYLIB', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pylib')))
sys.argv = sys.argv[1:]; runpy.run_path(sys.argv[0], run_name='__main__')
