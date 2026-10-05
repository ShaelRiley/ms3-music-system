#!/usr/bin/env python3
"""Build pinned external Surge Python bindings. Never copy them into the addon."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path
HERE=Path(__file__).resolve().parent
LOCK=json.loads((HERE/'lock.json').read_text())

def run(*args,cwd=None):
    subprocess.run(list(map(str,args)),cwd=cwd,check=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--build',type=Path,required=True)
    parser.add_argument('--jobs',type=int,default=4)
    parser.add_argument('--python-library',type=Path,help='Override a relocated Python shared library')
    args=parser.parse_args();source=args.source.resolve();build=args.build.resolve()
    repo=HERE.parents[2]
    if source==repo or repo in source.parents or build==repo or repo in build.parents:
        parser.error('Keep the external Surge source/build outside the game repository.')
    if not source.exists():run('git','clone','--depth','1','--branch',LOCK['tag'],LOCK['repository'],source)
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
    if head!=LOCK['commit']:raise RuntimeError('Wrong Surge source revision: '+head)
    patch=(HERE/'surgepy_lod.patch').read_bytes()
    if hashlib.sha256(patch).hexdigest()!=LOCK['bindingPatchSHA256']:raise RuntimeError('Binding patch differs from lock')
    diff=subprocess.check_output(['git','diff','--','src/surge-python/surgepy.cpp'],cwd=source)
    if not diff:run('git','apply',HERE/'surgepy_lod.patch',cwd=source)
    elif diff!=patch:raise RuntimeError('Unexpected local binding changes')
    changed=subprocess.check_output(['git','diff','--name-only'],cwd=source,text=True).splitlines()
    if changed!=['src/surge-python/surgepy.cpp']:raise RuntimeError('Unexpected external source changes: '+str(changed))
    run('git','submodule','update','--init','--recursive',cwd=source)
    cmake=shutil.which('cmake') or str(Path.home()/'.local/bin/cmake')
    library=args.python_library
    if not library:
        names=[sysconfig.get_config_var('LDLIBRARY'),sysconfig.get_config_var('INSTSONAME')]
        directories=[Path(sysconfig.get_config_var('LIBDIR') or ''),Path(sys.executable).resolve().parent.parent/'lib']
        library=next((d/n for d in directories for n in names if n and (d/n).is_file()),None)
    extra=['-DPYTHON_LIBRARY='+str(library.resolve())] if library else []
    run(cmake,'-S',source,'-B',build,'-DCMAKE_BUILD_TYPE=Release','-DCMAKE_POLICY_VERSION_MINIMUM=3.5',
        '-DSURGE_BUILD_PYTHON_BINDINGS=ON','-DSURGE_BUILD_XT=OFF','-DSURGE_BUILD_FX=OFF',
        '-DSURGE_BUILD_TESTRUNNER=OFF','-DSURGE_SKIP_JUCE_FOR_RACK=ON','-DSURGE_SKIP_LUA=ON',
        '-DSURGE_SKIP_ODDSOUND_MTS=ON','-DSURGE_SKIP_WERROR=ON','-DPYTHON_EXECUTABLE='+sys.executable,*extra)
    run(cmake,'--build',build,'--parallel',str(args.jobs),'--target','surgepy')
    print('Pass --surge-module',build/'src/surge-python','to build_ms2_surge.py')

if __name__=='__main__':main()
