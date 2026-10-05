#!/usr/bin/env node
// Explicit, actual committed-audio decode gate. No browser or live synthesizer.
'use strict';
const cp=require('child_process');const path=require('path');
const result=cp.spawnSync('python3',['tools/test_ms2_surge_bank.py','--decode'],{
 cwd:path.resolve(__dirname,'..'),encoding:'utf8',timeout:600000,maxBuffer:2*1024*1024
});
if(result.stdout)process.stdout.write(result.stdout);
if(result.stderr)process.stderr.write(result.stderr);
if(result.error){console.error(result.error.message);process.exit(1);}
process.exit(result.status===0?0:1);
