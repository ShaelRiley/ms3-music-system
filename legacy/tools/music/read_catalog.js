'use strict';
// Read JSON data from the shipped Lua-returned shards without evaluating Lua.
const fs=require('fs'),path=require('path');
const directory=path.resolve(__dirname,'../../gamemodes/legend_of_deborah/gamemode/lod/ms2');
function read(name) {return JSON.parse(fs.readFileSync(path.join(directory,name),'utf8').split('[==[')[1].split(']==]')[0]);}
const catalog=read('catalog.lua'),pages={};
function asset(id) {
    const a=catalog.assets[id];
    return {...a,clips:a.clips.map(c=>{
        if(!pages[c.page])pages[c.page]=read(c.page);
        return {...c,notes:pages[c.page][c.id]};
    })};
}
module.exports={catalog,asset,read};
