set -e
cd /c/Users/Admin/claude/schala-os
rm -rf build/d1h build/d1h_o build/d1h_e build/d1h_np build/d1h_np_bz build/d1h_np_bz_pl build/d1h_np_bz_pl_gb build/v046 build/v046_img
python tools/build_helpers.py build/amu build/d1h game/device/np_helpers.c game/device/np_stub.S game/device/libscan.c > build/b46.log
python tools/build_overlay.py build/d1h build/d1h_o game/device/npui.c --slot 28 --run 0x03083F0C --max 0x758 --at 0x5B400 --json npui.json >> build/b46.log
python tools/extend_module.py build/d1h_o build/d1h_e game/device/m21_ext.S game/device/m21_ext.c --module 21 --json e21.json
python tools/extend_module.py build/d1h_e build/d1h_e game/device/m22_ext.S game/device/m22_ext.c --module 22 --json e22.json
python tools/patch_code.py build/d1h_e build/d1h_np np_v4,np_hide_format,menu_games_to_blockz,lib_skip,menu_carousel,music_update,playlists,keep_settings,english,np_back_home > build/b46_patch.log
python tools/build_module.py build/d1h_np build/d1h_np_bz game/device/blockz.c --at 0x58800 >> build/b46.log 2>&1
python tools/build_module.py build/d1h_np_bz build/d1h_np_bz_pl game/device/playlists.c --module 86 --in-place --desc pl_desc --data-max 0xD00 >> build/b46.log 2>&1
python tools/build_module.py build/d1h_np_bz_pl build/d1h_np_bz_pl_gb game/device/gbprobe.c --module 87 --span 0x95578:0xa3ec0 --desc gb_desc --opt O2 --data-max 0xD00 >> build/b46.log 2>&1
python tools/build_reskin.py build/d1h_np_bz_pl_gb build/art_pocket_all 2620071146000000 --out build/v046 --font tall >> build/b46.log
echo BUILD OK
