#!/usr/bin/env python3
"""Package the lightweight rendered-phrase controller (no synthesizer dependency)."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def main():
    source=(ROOT/'tools/music/ms2_engine.js').read_text()
    (ROOT/'gamemodes/legend_of_deborah/gamemode/lod/ms2/engine.lua').write_text('return [==['+source+']==]\n')
    print('MS2 rendered-phrase controller:',len(source.encode()),'bytes')

if __name__=='__main__':main()
