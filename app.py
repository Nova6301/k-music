from flask import Flask, render_template_string, jsonify, request, send_from_directory, send_file
from waitress import serve
from ytmusicapi import YTMusic
from functools import lru_cache
import threading, yt_dlp, os, time, urllib.request, urllib.parse, json, re, uuid
import logging

# Logları temizle
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
logging.getLogger('waitress').setLevel(logging.ERROR)

app = Flask(__name__)

# --- MOTORLAR VE AYARLAR ---
ytmusic_instance = None
def get_ytmusic():
    global ytmusic_instance
    if ytmusic_instance is None:
        ytmusic_instance = YTMusic()
    return ytmusic_instance

ydl_opts = {'format': 'bestaudio[ext=m4a]/bestaudio/best', 'quiet': True, 'noplaylist': True, 'no_warnings': True}
ydl_engine = yt_dlp.YoutubeDL(ydl_opts)

DOWNLOAD_FOLDER = "k_cache"
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# --- ARAYÜZ (HTML/CSS/JS) - MOBİL İÇİN OPTİMİZE EDİLDİ ---
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>K Music</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@800;900&family=Plus+Jakarta+Sans:wght@300;400;600;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --bg: #050505; --sidebar: #000000; --card: #121212; --accent: #ffffff;
            --text-main: #ffffff; --text-sub: #a7a7a7; --radius-lg: 30px; --radius-sm: 15px;
            --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        * { margin: 0; padding: 0; box-sizing: border-box; outline: none; -webkit-tap-highlight-color: transparent; }
        body { font-family: 'Plus Jakarta Sans', sans-serif; background: var(--bg); color: var(--text-main); height: 100vh; overflow: hidden; display: flex; flex-direction: column; margin: 0; }

        /* Masaüstü barları gizlendi, tam ekran web/mobil deneyimi */
        .titlebar { display: none !important; }

        .layout { flex: 1; display: grid; grid-template-columns: 280px 1fr; padding: 12px; gap: 12px; overflow: hidden; transition: var(--transition); }
        .sidebar { background: var(--sidebar); border-radius: var(--radius-lg); padding: 30px 20px; display: flex; flex-direction: column; gap: 8px; border: 1px solid #1a1a1a; overflow-y: auto; scrollbar-width: none; }
        .logo { font-family: 'Outfit', sans-serif; font-size: 28px; font-weight: 900; letter-spacing: -0.5px; margin-bottom: 30px; padding-left: 15px; color: #ffffff; }
        .logo-music { background: linear-gradient(135deg, #d7d7d7 0%, #666666 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }

        .nav-head { display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: #555; font-weight: 800; padding: 10px 15px; margin-top: 15px; letter-spacing: 1px; }
        .nav-head i { font-size: 14px; cursor: pointer; color: var(--text-sub); transition: 0.2s; }
        .nav-head i:hover { color: #ffffff; transform: scale(1.2); }
        .nav-item { padding: 14px 20px; border-radius: var(--radius-sm); color: var(--text-sub); cursor: pointer; display: flex; align-items: center; justify-content: flex-start; gap: 15px; transition: var(--transition); font-weight: 600; font-size: 14px; }
        .nav-item:hover, .nav-item.active { background: #1a1a1a; color: white; }
        .nav-item i.left-icon { width: 20px; text-align: center; }

        .content { background: linear-gradient(180deg, #1a1a1a 0%, #050505 100%); border-radius: var(--radius-lg); padding: 40px; overflow-y: auto; position: relative; scrollbar-width: none; margin-bottom: 90px; transition: var(--transition); }
        .search-container { position: sticky; top: 0; z-index: 100; display: flex; align-items: center; gap: 20px; margin-bottom: 40px; }
        .search-box { background: rgba(255,255,255,0.1); backdrop-filter: blur(20px); border-radius: 50px; padding: 14px 25px; display: flex; align-items: center; gap: 15px; width: 450px; border: 1px solid rgba(255,255,255,0.05); transition: var(--transition); }
        .search-box:focus-within { width: 500px; background: rgba(255,255,255,0.15); border-color: #444; }
        .search-box input { background: none; border: none; color: white; width: 100%; font-size: 15px; transition: 0.3s; }

        #loaderText { display: none; align-items: center; gap: 8px; color: #ffffff; font-weight: 600; font-size: 14px; opacity: 0.8; letter-spacing: 0.5px; animation: fadeIn 0.3s ease-in-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateX(-10px); } to { opacity: 0.8; transform: translateX(0); } }

        .history-list { display: flex; flex-direction: column; gap: 10px; max-width: 600px; }
        .history-item { background: rgba(255,255,255,0.03); padding: 15px 20px; border-radius: 12px; display: flex; align-items: center; justify-content: space-between; cursor: pointer; transition: 0.2s; font-weight: 600; border: 1px solid rgba(255,255,255,0.02); }
        .history-item:hover { background: rgba(255,255,255,0.08); transform: translateX(5px); border-color: #ffffff; color: #ffffff; }

        .song-list { display: flex; flex-direction: column; gap: 5px; }
        .song-item { display: flex; align-items: center; padding: 12px 20px; border-radius: var(--radius-sm); transition: var(--transition); cursor: pointer; border: 1px solid transparent; }
        .song-item:hover { background: rgba(255,255,255,0.05); transform: scale(1.01); border-color: rgba(255,255,255,0.1); }
        .song-item img { width: 52px; height: 52px; border-radius: 10px; margin-right: 20px; object-fit: cover; }
        .song-info { flex: 1; overflow: hidden; }
        .song-title { font-weight: 700; font-size: 15px; margin-bottom: 4px; white-space: nowrap; text-overflow: ellipsis; overflow: hidden; }
        .song-artist { color: var(--text-sub); font-size: 13px; }
        
        .item-actions { display: flex; gap: 15px; color: var(--text-sub); align-items: center; position: relative; }
        .item-actions i { padding: 5px; transition: 0.2s; cursor: pointer; }
        .item-actions i.fa-plus:hover { color: #ffffff; transform: scale(1.2); }
        .item-actions i.fa-heart:hover { color: #ffffff; transform: scale(1.2); }
        .item-actions i.fa-download:hover { color: #ffffff; transform: scale(1.2); }
        .item-actions i.fa-check:hover { color: #ffffff; } 

        .playlist-menu { position: fixed; background: #111; border: 1px solid #333; border-radius: 15px; padding: 10px; z-index: 1000; box-shadow: 0 10px 40px rgba(0,0,0,0.9); display: none; flex-direction: column; gap: 5px; min-width: 180px; }
        .playlist-menu-item { padding: 10px 15px; border-radius: 10px; cursor: pointer; color: #ccc; font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 10px; transition: 0.2s; }
        .playlist-menu-item:hover { background: #ffffff; color: black; }

        .lyrics-box { white-space: pre-wrap; text-align: center; font-size: 18px; line-height: 2; color: #ddd; max-width: 800px; margin: 0 auto; padding: 20px; font-weight: 600; }
        .lyrics-subtitle { text-align: center; color: var(--text-sub); font-size: 14px; margin-bottom: 30px; font-weight: 600; }

        .player-bar { position: fixed; bottom: 30px; left: 310px; right: 30px; background: rgba(10, 10, 10, 0.95); backdrop-filter: blur(30px); border-radius: 25px; padding: 15px 35px; display: flex; align-items: center; justify-content: space-between; border: 1px solid rgba(255,255,255,0.08); box-shadow: 0 20px 50px rgba(0,0,0,0.5); z-index: 500; transition: var(--transition); }
        .p-meta { display: flex; align-items: center; gap: 18px; width: 30%; overflow: hidden; }
        .p-meta img { width: 60px; height: 60px; border-radius: 12px; box-shadow: 0 8px 20px rgba(0,0,0,0.4); }
        
        .p-center { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 10px; }
        .p-btns { display: flex; align-items: center; gap: 20px; }
        .play-trigger { width: 50px; height: 50px; border-radius: 50%; background: white; color: black; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 20px; transition: var(--transition); }
        .play-trigger:hover { transform: scale(1.1); }
        
        .visualizer { display: flex; align-items: flex-end; justify-content: center; gap: 3px; height: 24px; width: 40px; margin-left: 15px; opacity: 0; transition: opacity 0.3s; }
        .visualizer.active { opacity: 1; }
        .vis-bar { width: 5px; background: #ffffff; border-radius: 2px; height: 3px; transition: height 0.08s ease; }

        .progress-container { width: 100%; max-width: 600px; display: flex; align-items: center; gap: 15px; font-size: 11px; color: var(--text-sub); font-weight: 600; }
        .progress-rail { flex: 1; height: 5px; background: #2a2a2a; border-radius: 10px; cursor: pointer; position: relative; overflow: hidden; }
        .progress-track { height: 100%; background: white; width: 0%; transition: 0.1s linear; pointer-events: none; }

        .p-right { width: 30%; display: flex; justify-content: flex-end; align-items: center; gap: 15px; color: var(--text-sub); font-size: 18px; }

        .vol-wrapper { display: flex; align-items: center; gap: 10px; position: relative; }
        .vol-wrapper i { font-size: 16px; color: #a7a7a7; transition: 0.2s; cursor: pointer; width: 22px; text-align: center; }
        .vol-wrapper i:hover { color: #ffffff; }

        #volSlider { -webkit-appearance: none; width: 80px; height: 5px; border-radius: 10px; background: linear-gradient(to right, white 100%, #2a2a2a 100%); cursor: pointer; border: none; outline: none; }
        #volSlider::-webkit-slider-thumb { -webkit-appearance: none; height: 12px; width: 12px; border-radius: 50%; background: white; cursor: pointer; border: none; }
        
        .action-group { display: flex; gap: 18px; padding-right: 20px; border-right: 1px solid rgba(255,255,255,0.1); align-items: center; }
        .action-group i { font-size: 16px; cursor: pointer; color: #777; transition: 0.2s; }
        .action-group i:hover { color: white; transform: scale(1.1); }
        .action-group i.fa-check { color: #ffffff !important; }
        
        .refresh-btn { font-size:20px; cursor:pointer; color:#777; transition:0.3s; }
        .refresh-btn:hover { color:#ffffff; transform:rotate(180deg); }

        .modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0, 0, 0, 0.7); backdrop-filter: blur(8px); z-index: 10000; display: none; align-items: center; justify-content: center; opacity: 0; transition: opacity 0.3s ease; }
        .modal-overlay.active { display: flex; opacity: 1; }
        .modal-content { background: #111; border-radius: 20px; padding: 30px; width: 350px; border: 1px solid rgba(255,255,255,0.05); box-shadow: 0 20px 50px rgba(0,0,0,0.8); transform: scale(0.9); transition: transform 0.3s ease; }
        .modal-overlay.active .modal-content { transform: scale(1); }
        .modal-title { font-size: 20px; font-weight: 800; margin-bottom: 20px; color: white; }
        .modal-input { width: 100%; background: #050505; border: 1px solid #333; color: white; padding: 14px 20px; border-radius: 12px; font-size: 14px; margin-bottom: 25px; outline: none; transition: 0.2s; font-family: 'Plus Jakarta Sans', sans-serif; }
        .modal-input:focus { border-color: #555; background: #1a1a1a; box-shadow: 0 0 10px rgba(255,255,255,0.05); }
        .modal-actions { display: flex; justify-content: flex-end; gap: 12px; }
        .btn-modal { padding: 10px 20px; border-radius: 10px; font-weight: 600; cursor: pointer; border: none; font-size: 13px; font-family: 'Plus Jakarta Sans', sans-serif; transition: 0.2s; }
        .btn-cancel { background: transparent; color: var(--text-sub); }
        .btn-cancel:hover { color: white; background: rgba(255,255,255,0.05); }
        .btn-create { background: white; color: black; }
        .btn-create:hover { background: #e0e0e0; transform: translateY(-2px); }

        .eq-menu { position: absolute; bottom: 40px; right: 0; background: #111; border: 1px solid #333; border-radius: 15px; padding: 20px 20px 15px 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.9); display: none; flex-direction: column; gap: 15px; width: 220px; z-index: 1000; }
        .eq-menu label { font-size: 12px; font-weight: 600; color: #ccc; display: flex; justify-content: space-between; }
        .eq-slider { -webkit-appearance: none; width: 100%; height: 4px; border-radius: 5px; background: #333; outline: none; }
        .eq-slider::-webkit-slider-thumb { -webkit-appearance: none; width: 12px; height: 12px; border-radius: 50%; background: #ffffff; cursor: pointer; }
        .eq-note { font-size: 10px; color: #666; text-align: center; margin-top: 5px; line-height: 1.3; font-weight: 400; }

        /* MOBİL RESPONSIVE (APK GÖRÜNÜMÜ) */
        @media screen and (max-width: 768px) {
            .layout { display: flex; flex-direction: column; padding: 15px; margin-bottom: 80px; gap: 20px; }
            
            /* Sol menüyü Spotify gibi Alt Bara çevirdik */
            .sidebar { 
                position: fixed; bottom: 0; left: 0; right: 0; height: 70px; 
                flex-direction: row; justify-content: space-around; align-items: center;
                border-radius: 0; border: none; border-top: 1px solid #1a1a1a;
                padding: 0 10px; z-index: 1000; background: #050505;
            }
            .logo, .nav-head, #customPlaylistsContainer, #miniToggleBtn { display: none !important; }
            .nav-item { flex-direction: column; gap: 5px; padding: 10px 5px; font-size: 11px; min-width: 60px; justify-content: center; border-radius: 10px; }
            .nav-item i { width: auto; font-size: 18px; margin: 0; }
            
            .content { border-radius: 20px; padding: 20px; margin-bottom: 0; }
            .search-box { width: 100%; }
            .search-box:focus-within { width: 100%; }
            
            /* Mobil Player Bar */
            .player-bar { 
                left: 10px; right: 10px; bottom: 80px; padding: 10px 15px; 
                border-radius: 20px; background: rgba(20,20,20,0.98); flex-wrap: wrap; justify-content: center;
            }
            .p-meta { width: 100%; margin-bottom: 10px; justify-content: center;}
            .p-meta img { width: 45px; height: 45px; }
            .p-center { width: 100%; }
            .p-btns { gap: 15px; }
            .play-trigger { width: 40px; height: 40px; font-size: 16px; }
            
            .p-right, .action-group, .progress-container, .visualizer { display: none !important; }
        }
    </style>
</head>
<body>
    <div class="modal-overlay" id="playlistModal">
        <div class="modal-content">
            <div class="modal-title">Yeni Çalma Listesi</div>
            <input type="text" class="modal-input" id="playlistNameInput" placeholder="Örn: Çalışırken, Yol Şarkıları..." onkeyup="if(event.key==='Enter') submitPlaylist()">
            <div class="modal-actions">
                <button class="btn-modal btn-cancel" onclick="closePlaylistModal()">İptal</button>
                <button class="btn-modal btn-create" onclick="submitPlaylist()">Oluştur</button>
            </div>
        </div>
    </div>

    <div id="plMenu" class="playlist-menu"></div>

    <div class="layout">
        <aside class="sidebar">
            <div class="nav-item active" onclick="showView('home')"><i class="fas fa-rocket left-icon"></i> <div>Keşfet</div></div>
            <div class="nav-item" onclick="showView('searchTab')"><i class="fas fa-search left-icon"></i> <div>Ara</div></div>
            <div class="nav-item" onclick="showView('favs')"><i class="fas fa-heart left-icon"></i> <div>Favoriler</div></div>
            <div class="nav-item" onclick="showView('downloads')"><i class="fas fa-download left-icon"></i> <div>İndirilenler</div></div>
            
            <div class="nav-head">ÇALMA LİSTELERİ <i class="fas fa-plus" onclick="openPlaylistModal()"></i></div>
            <div id="customPlaylistsContainer"></div>
        </aside>

        <main class="content">
            <div class="search-container">
                <div class="search-box">
                    <i class="fas fa-search" id="sIcon" style="color:#555"></i>
                    <input type="text" id="sInp" placeholder="Sınırsız müzik ara..." onkeyup="if(event.key==='Enter') { startSearch(this.value); this.blur(); }">
                </div>
                <div id="loaderText">Aranıyor...</div>
            </div>

            <div id="view-home">
                <div style="display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:30px">
                    <div>
                        <h2 style="font-size:32px;">Sizin İçin</h2>
                        <div id="discoverSubtitle" style="color:var(--text-sub); font-size:14px; font-weight:600; margin-top:5px;">Özel miksiniz hazırlanıyor...</div>
                    </div>
                    <i class="fas fa-sync-alt refresh-btn" onclick="loadDiscover()" title="Tazele"></i>
                </div>
                <div class="song-list" id="homeList"></div>
            </div>

            <div id="view-search-history" style="display:none">
                <div style="display:flex; justify-content:space-between; margin-bottom:30px">
                    <h2 style="font-size:32px;">Son Aramalar</h2>
                    <div style="cursor:pointer; color:#ffffff" onclick="clearSearchHistory()">Temizle</div>
                </div>
                <div class="history-list" id="historyList"></div>
            </div>

            <div id="view-search" style="display:none">
                <h2 id="searchTitle" style="margin-bottom:30px">Sonuçlar</h2>
                <div class="song-list" id="searchList"></div>
            </div>

            <div id="view-lyrics" style="display:none">
                <h2 id="lyricsTitle" style="text-align:center; margin-bottom: 5px;">Sözler</h2>
                <div class="lyrics-subtitle" id="lyricsSubtitle"></div>
                <div class="lyrics-box" id="lyricsText">Yükleniyor...</div>
            </div>
        </main>

        <footer class="player-bar">
            <div class="p-meta">
                <img id="pImg" src="" style="display:none">
                <div>
                    <div id="pTitle" style="font-weight:800; font-size:15px; white-space:nowrap; overflow:hidden">Parça Seçilmedi</div>
                    <div id="pArtist" style="color:var(--text-sub); font-size:12px">K Music Engine</div>
                </div>
            </div>
            <div class="p-center">
                <div class="p-btns">
                    <div class="action-group">
                        <i class="fas fa-plus" onclick="openPlaylistMenu(event, -1)" title="Listeye Ekle"></i>
                        <i class="fas fa-download" id="playerDlBtn" onclick="downloadTrack(event, -1)" title="İndir"></i>
                        <i class="fas fa-align-left" onclick="fetchLyrics()" title="Şarkı Sözleri"></i>
                    </div>
                    <i class="fas fa-backward-step" onclick="playPrev()" style="font-size:18px; cursor:pointer; color:#777; transition:0.2s;"></i>
                    <button class="play-trigger" id="mainPlayBtn" onclick="togglePlay()"><i id="pIcon" class="fas fa-play"></i></button>
                    <i class="fas fa-forward-step" onclick="playNext()" style="font-size:18px; cursor:pointer; color:#777; transition:0.2s;"></i>
                    <div class="visualizer" id="visBox"><div class="vis-bar"></div><div class="vis-bar"></div><div class="vis-bar"></div><div class="vis-bar"></div><div class="vis-bar"></div></div>
                </div>
                <div class="progress-container">
                    <span id="curTime">0:00</span>
                    <div class="progress-rail" onclick="seekTrack(event)"><div class="progress-track" id="trackFill"></div></div>
                    <span id="durTime">0:00</span>
                </div>
            </div>
            <div class="p-right">
                <div class="vol-wrapper">
                    <i class="fas fa-sliders-h" id="eqBtn" onclick="toggleEqMenu()" title="Ekolayzer"></i>
                    <div class="eq-menu" id="eqMenu">
                        <label>Bas <span id="bassVal">0</span></label>
                        <input type="range" class="eq-slider" id="bassSlider" min="-15" max="15" value="0" oninput="updateEq()">
                        <label>Tiz <span id="trebleVal">0</span></label>
                        <input type="range" class="eq-slider" id="trebleSlider" min="-15" max="15" value="0" oninput="updateEq()">
                        <div class="eq-note">* Sadece indirilen müziklerde etkilidir.</div>
                    </div>
                    <i class="fas fa-volume-up" id="muteBtn" onclick="toggleMute()" style="margin-left:10px"></i>
                    <input type="range" id="volSlider" min="0" max="100" value="100" oninput="changeVol(this.value)">
                </div>
            </div>
        </footer>
    </div>

    <script>
        let playerA = new Audio(); let playerB = new Audio();
        let currentPlayer = playerA; let globalVolume = 1.0;
        
        let currentList = []; let homeTracks = []; let nowPlaying = null;
        let activeTrackIndex = -1; let visInterval = null; 
        
        let library = JSON.parse(localStorage.getItem('k_library_v2')) || { 'favs': [], 'downloads': [] };
        if(!library['downloads']) library['downloads'] = [];
        
        let searchHistory = JSON.parse(localStorage.getItem('k_search_history')) || [];
        let isMuted = false; let preMuteVolume = 1.0;

        if ('mediaSession' in navigator) {
            navigator.mediaSession.setActionHandler('play', togglePlay);
            navigator.mediaSession.setActionHandler('pause', togglePlay);
            navigator.mediaSession.setActionHandler('previoustrack', playPrev);
            navigator.mediaSession.setActionHandler('nexttrack', playNext);
        }

        window.addEventListener('keydown', (e) => {
            if(document.activeElement && document.activeElement.tagName === 'INPUT') return; 
            if(e.code === 'Space' || e.key === ' ') { e.preventDefault(); togglePlay(); }
            else if (e.key === 'MediaPlayPause') togglePlay();
            else if (e.key === 'MediaTrackNext' || e.code === 'ArrowRight') playNext();
            else if (e.key === 'MediaTrackPrevious' || e.code === 'ArrowLeft') playPrev();
        });

        document.addEventListener('click', (e) => {
            let eqM = document.getElementById('eqMenu');
            let eqB = document.getElementById('eqBtn');
            if(eqM && eqM.style.display === 'flex' && !eqM.contains(e.target) && e.target !== eqB) {
                eqM.style.display = 'none';
            }
        });

        function setupPlayer(p) {
            p.addEventListener('timeupdate', () => {
                if(p === currentPlayer && p.duration) {
                    document.getElementById('trackFill').style.width = (p.currentTime / p.duration * 100) + '%';
                    document.getElementById('curTime').innerText = formatTime(p.currentTime);
                    document.getElementById('durTime').innerText = formatTime(p.duration);
                }
            });
            p.addEventListener('ended', () => { if(p === currentPlayer) playNext(); });
        }
        setupPlayer(playerA); setupPlayer(playerB);

        window.onload = () => { renderSidebarPlaylists(); setTimeout(loadDiscover, 300); };

        function toggleEqMenu() {
            let m = document.getElementById('eqMenu');
            m.style.display = m.style.display === 'flex' ? 'none' : 'flex';
        }
        
        function updateEq() {
            let b = document.getElementById('bassSlider').value;
            let t = document.getElementById('trebleSlider').value;
            document.getElementById('bassVal').innerText = b;
            document.getElementById('trebleVal').innerText = t;
        }

        function isDownloaded(track) {
            if(!track || !library['downloads']) return false;
            let targetUrl = track.original_url || track.url;
            return library['downloads'].some(d => (d.original_url || d.url) === targetUrl);
        }

        async function downloadTrack(event, i) {
            event.stopPropagation();
            let track = (i === -1) ? nowPlaying : currentList[i];
            if(!track || track.url === 'local_pc') return; 
            
            let isPlayer = (i === -1); let icon = event.target;
            
            if(isDownloaded(track)) {
                let targetUrl = track.original_url || track.url;
                library['downloads'] = library['downloads'].filter(d => (d.original_url || d.url) !== targetUrl);
                localStorage.setItem('k_library_v2', JSON.stringify(library));
                icon.className = 'fas fa-download'; icon.style.color = isPlayer ? '#777' : 'var(--text-sub)';
                if(document.getElementById('searchTitle').innerText === "İndirilenler") showView('downloads');
                return;
            }

            let oldClass = icon.className; icon.className = 'fas fa-spinner fa-spin'; icon.style.color = '#ffffff';
            try {
                let res = await fetch('/api/download_track', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(track) });
                let data = await res.json();
                if(data.success) {
                    icon.className = 'fas fa-check'; icon.style.color = '#ffffff';
                    let localTrack = { ...track, url: 'local', original_url: track.url, local_filename: data.local_filename };
                    library['downloads'].push(localTrack); localStorage.setItem('k_library_v2', JSON.stringify(library));
                    if(!isPlayer && nowPlaying && (nowPlaying.url === track.url || nowPlaying.original_url === track.url)) {
                        let pdl = document.getElementById('playerDlBtn'); pdl.className = 'fas fa-check'; pdl.style.color = '#ffffff';
                    }
                } else { icon.className = oldClass; alert("İndirme başarısız."); }
            } catch (e) { icon.className = oldClass; }
        }

        function loadDiscover() {
            let seeds = ["Top Hits", "Global Top 50", "Viral Müzikler", "Pop Hits", "Türkçe Pop"];
            let userPool = [];
            if (searchHistory && searchHistory.length > 0) userPool = userPool.concat(searchHistory);
            if (library['favs'] && library['favs'].length > 0) library['favs'].forEach(t => { if(t.artist && t.artist !== 'Bilinmeyen') userPool.push(t.artist); });
            
            let query = "", seedName = "";
            if (userPool.length > 0) {
                userPool = [...new Set(userPool)];
                seedName = userPool[Math.floor(Math.random() * userPool.length)];
                query = seedName + " mix"; 
            } else {
                seedName = seeds[Math.floor(Math.random() * seeds.length)];
                query = seedName; seedName = ""; 
            }
            startSearch(query, true, seedName);
        }

        async function startSearch(q, isHome = false, seedName = "") {
            if(!q) return;
            if(!isHome) {
                searchHistory = [q, ...searchHistory.filter(i => i !== q)].slice(0,15);
                localStorage.setItem('k_search_history', JSON.stringify(searchHistory));
                document.getElementById('sIcon').className = "fas fa-circle-notch fa-spin"; document.getElementById('loaderText').style.display = "flex";
            } else {
                document.getElementById('discoverSubtitle').innerText = seedName ? `'${seedName}' dinlemelerinden ilham alındı` : "Bugün senin için seçtiklerimiz";
                document.getElementById('homeList').innerHTML = '<div style="color:#555; margin-top:20px; font-weight:600;"><i class="fas fa-spinner fa-spin"></i> Taranıyor...</div>';
            }
            
            const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
            const data = await res.json();
            
            if(!isHome) { document.getElementById('sIcon').className = "fas fa-search"; document.getElementById('loaderText').style.display = "none"; }
            currentList = data.results;
            if(isHome) { homeTracks = currentList; showView('home'); renderList('homeList', currentList); }
            else { showView('search'); document.getElementById('searchTitle').innerText = `"${q}" sonuçları`; renderList('searchList', currentList); }
        }

        async function playIndex(i) {
            const track = currentList[i];
            nowPlaying = track; activeTrackIndex = i;
            
            document.getElementById('pTitle').innerText = track.title;
            document.getElementById('pArtist').innerText = track.artist;
            document.getElementById('pImg').src = track.thumbnail;
            document.getElementById('pImg').style.display = 'block';
            document.getElementById('pIcon').className = 'fas fa-spinner fa-spin';

            let pdl = document.getElementById('playerDlBtn');
            if(track.url === 'local_pc') { pdl.style.display = 'none'; }
            else { pdl.style.display = 'inline-block'; let isD = isDownloaded(track); pdl.className = isD ? 'fas fa-check' : 'fas fa-download'; pdl.style.color = isD ? '#ffffff' : '#777'; }

            if ('mediaSession' in navigator) navigator.mediaSession.metadata = new MediaMetadata({ title: track.title, artist: track.artist, artwork: [{ src: track.thumbnail, sizes: '512x512', type: 'image/jpeg' }]});

            const res = await fetch('/api/play', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(track) });
            const data = await res.json();
            
            if(data.success) {
                let nextPlayer = (currentPlayer === playerA) ? playerB : playerA;
                nextPlayer.src = data.stream_url; 
                nextPlayer.volume = globalVolume;
                
                nextPlayer.play().then(() => {
                    if (!currentPlayer.paused && currentPlayer.src) {
                        let oldP = currentPlayer;
                        let f = setInterval(() => { if(oldP.volume > 0.1) oldP.volume -= 0.1; else { clearInterval(f); oldP.pause(); oldP.src=""; } }, 50);
                    }
                    currentPlayer = nextPlayer; document.getElementById('pIcon').className = 'fas fa-pause'; startVisualizer();
                }).catch(err => {
                    console.error("Oynatma hatası:", err);
                    document.getElementById('pIcon').className = 'fas fa-play';
                });
            }
        }

        function togglePlay() {
            const btn = document.getElementById('mainPlayBtn');
            if(!nowPlaying) { btn.classList.add('glitch-active'); setTimeout(() => btn.classList.remove('glitch-active'), 300); return; }
            if(currentPlayer.paused) { currentPlayer.play(); document.getElementById('pIcon').className = 'fas fa-pause'; startVisualizer(); }
            else { currentPlayer.pause(); document.getElementById('pIcon').className = 'fas fa-play'; stopVisualizer(); }
        }

        function startVisualizer() { if(visInterval) clearInterval(visInterval); document.getElementById('visBox').classList.add('active'); visInterval = setInterval(() => { document.querySelectorAll('.vis-bar').forEach(b => { b.style.height = (Math.random() * 20 * globalVolume + 4) + 'px'; }); }, 100); }
        function stopVisualizer() { clearInterval(visInterval); document.getElementById('visBox').classList.remove('active'); }
        function seekTrack(e) { if(nowPlaying && currentPlayer.duration) currentPlayer.currentTime = (e.offsetX / e.target.clientWidth) * currentPlayer.duration; }
        
        function changeVol(v) {
            const volVal = v / 100; globalVolume = volVal; currentPlayer.volume = globalVolume;
            const slider = document.getElementById('volSlider'); slider.style.background = `linear-gradient(to right, white ${v}%, #2a2a2a ${v}%)`;
            const muteBtn = document.getElementById('muteBtn');
            if (volVal === 0) { isMuted = true; muteBtn.className = 'fas fa-volume-mute'; }
            else if (volVal < 0.5) { isMuted = false; muteBtn.className = 'fas fa-volume-down'; }
            else { isMuted = false; muteBtn.className = 'fas fa-volume-up'; }
        }

        function toggleMute() {
            const muteBtn = document.getElementById('muteBtn'); const slider = document.getElementById('volSlider');
            if (isMuted) {
                globalVolume = preMuteVolume; currentPlayer.volume = globalVolume; muteBtn.className = globalVolume < 0.5 ? 'fas fa-volume-down' : 'fas fa-volume-up'; isMuted = false;
                slider.value = preMuteVolume * 100; slider.style.background = `linear-gradient(to right, white ${preMuteVolume * 100}%, #2a2a2a ${preMuteVolume * 100}%)`;
            } else {
                preMuteVolume = globalVolume; globalVolume = 0; currentPlayer.volume = 0; muteBtn.className = 'fas fa-volume-mute'; isMuted = true;
                slider.value = 0; slider.style.background = `linear-gradient(to right, white 0%, #2a2a2a 0%)`;
            }
        }

        function formatTime(s) { if(isNaN(s)) return "0:00"; let m=Math.floor(s/60), sec=Math.floor(s%60); return m+":"+(sec<10?"0":"")+sec; }
        
        function renderList(id, tracks) {
            const c = document.getElementById(id); c.innerHTML = '';
            tracks.forEach((t, i) => {
                const isF = library['favs'].some(f => f.url === t.url || f.original_url === t.url);
                const isD = isDownloaded(t);
                let dlBtnHTML = '';
                if(t.url !== 'local_pc') {
                    const dlClass = isD ? 'fas fa-check' : 'fas fa-download';
                    const dlColor = isD ? '#ffffff' : '';
                    dlBtnHTML = `<i class="${dlClass}" style="color:${dlColor}" onclick="downloadTrack(event, ${i})" title="İndir/Sil"></i>`;
                }

                c.innerHTML += `<div class="song-item" onclick="playIndex(${i})">
                    <img src="${t.thumbnail}"><div class="song-info"><div class="song-title">${t.title}</div><div class="song-artist">${t.artist}</div></div>
                    <div class="item-actions">
                        ${dlBtnHTML}
                        <i class="fas fa-plus" onclick="openPlaylistMenu(event, ${i})" title="Listeye Ekle"></i>
                        <i class="fa${isF?'s':'r'} fa-heart" style="${isF?'color:#ffffff':''}" onclick="event.stopPropagation(); toggleFavItem(${i})" title="Favori"></i>
                    </div>
                </div>`;
            });
        }

        function showView(v, ln=null) {
            ['view-home','view-search','view-search-history','view-lyrics'].forEach(id => document.getElementById(id).style.display='none');
            document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
            if(v==='home') { document.getElementById('view-home').style.display='block'; document.querySelectorAll('.nav-item')[0].classList.add('active'); currentList=homeTracks; }
            else if(v==='searchTab') { document.getElementById('view-search-history').style.display='block'; document.querySelectorAll('.nav-item')[1].classList.add('active'); renderHistory(); }
            else if(v==='search') { document.getElementById('view-search').style.display='block'; document.querySelectorAll('.nav-item')[1].classList.add('active'); }
            else if(v==='favs') { document.getElementById('view-search').style.display='block'; document.querySelectorAll('.nav-item')[2].classList.add('active'); document.getElementById('searchTitle').innerText="Favoriler"; currentList=library['favs']; renderList('searchList', currentList); }
            else if(v==='downloads') { document.getElementById('view-search').style.display='block'; document.querySelectorAll('.nav-item')[3].classList.add('active'); document.getElementById('searchTitle').innerText="İndirilenler"; currentList=library['downloads'] || []; renderList('searchList', currentList); }
            else if(v==='list') { document.getElementById('view-search').style.display='block'; document.getElementById('searchTitle').innerText=ln; currentList=library[ln]; renderList('searchList', currentList); }
        }

        function openPlaylistModal() { const m = document.getElementById('playlistModal'); const i = document.getElementById('playlistNameInput'); i.value = ''; m.classList.add('active'); setTimeout(() => i.focus(), 100); }
        function closePlaylistModal() { document.getElementById('playlistModal').classList.remove('active'); }
        function submitPlaylist() { const i = document.getElementById('playlistNameInput'); let n = i.value.trim(); if (n && !library[n]) { library[n] = []; localStorage.setItem('k_library_v2', JSON.stringify(library)); renderSidebarPlaylists(); closePlaylistModal(); } else if (library[n]) { i.style.borderColor = "#ffffff"; setTimeout(() => i.style.borderColor = "#333", 1000); } }
        function openPlaylistMenu(event, i) { event.stopPropagation(); let track = (i === -1) ? nowPlaying : currentList[i]; if(!track) return; let menu = document.getElementById('plMenu'); menu.innerHTML = ''; let lists = Object.keys(library).filter(k => k !== 'favs' && k !== 'downloads'); if(lists.length === 0) { menu.innerHTML = '<div style="color:#777; font-size:12px; padding:5px; text-align:center;">Önce yanda + ile bir liste oluşturun.</div>'; } else { lists.forEach(k => { menu.innerHTML += `<div class="playlist-menu-item" onclick="addToPlaylist('${k}', ${i})"><i class="fas fa-list"></i> ${k}</div>`; }); } menu.style.display = 'flex'; menu.style.left = event.clientX + 'px'; menu.style.top = (event.clientY - 30) + 'px'; setTimeout(() => { document.addEventListener('click', function closeMenu() { menu.style.display = 'none'; document.removeEventListener('click', closeMenu); }); }, 10); }
        function addToPlaylist(listName, i) { let track = (i === -1) ? nowPlaying : currentList[i]; if(!library[listName].some(t => (t.original_url || t.url) === (track.original_url || track.url))) { library[listName].push(track); localStorage.setItem('k_library_v2', JSON.stringify(library)); } }
        function renderSidebarPlaylists() { let c = document.getElementById('customPlaylistsContainer'); c.innerHTML=''; for(let k in library) if(k!=='favs' && k!=='downloads') c.innerHTML += `<div class="nav-item" onclick="showView('list', '${k}')"><i class="fas fa-list left-icon"></i><div>${k}</div></div>`; }
        function toggleFavItem(i) { let t=currentList[i], targetUrl=(t.original_url||t.url), idx=library['favs'].findIndex(f=>(f.original_url||f.url)===targetUrl); if(idx>-1) library['favs'].splice(idx,1); else library['favs'].push(t); localStorage.setItem('k_library_v2', JSON.stringify(library)); renderList(document.getElementById('view-search').style.display==='none'?'homeList':'searchList', currentList); }
        function playNext() { if(nowPlaying && currentList.length) playIndex((activeTrackIndex+1)%currentList.length); }
        function playPrev() { if(!nowPlaying || currentList.length === 0) return; if(currentPlayer.currentTime > 3) currentPlayer.currentTime = 0; else { let prevIdx = activeTrackIndex - 1; if(prevIdx < 0) prevIdx = currentList.length - 1; playIndex(prevIdx); } }

        async function fetchLyrics() { 
            if(!nowPlaying) return; document.getElementById('view-lyrics').style.display='block'; document.getElementById('view-home').style.display='none'; document.getElementById('view-search').style.display='none';
            document.getElementById('lyricsTitle').innerText = "Sözler"; document.getElementById('lyricsSubtitle').innerText = nowPlaying.artist + " - " + nowPlaying.title; document.getElementById('lyricsText').innerText = "Yükleniyor..."; 
            let r=await fetch(`/api/lyrics?artist=${encodeURIComponent(nowPlaying.artist)}&title=${encodeURIComponent(nowPlaying.title)}`); 
            let d=await r.json(); 
            if(d.cleaned_title) { document.getElementById('lyricsSubtitle').innerText = d.cleaned_title; }
            document.getElementById('lyricsText').innerText = d.lyrics; 
        }

        function renderHistory() { let c=document.getElementById('historyList'); c.innerHTML=''; if(!searchHistory.length) { c.innerHTML='<div style="color:#555">Boş.</div>'; return; } searchHistory.forEach(q => c.innerHTML+=`<div class="history-item" onclick="document.getElementById('sInp').value='${q}'; startSearch('${q}')"><div><i class="fas fa-clock"></i> ${q}</div><i class="fas fa-chevron-right"></i></div>`); }
        function clearSearchHistory() { searchHistory=[]; localStorage.removeItem('k_search_history'); renderHistory(); }
    </script>
</body>
</html>
'''

@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

@lru_cache(maxsize=30)
def cached_ytmusic_search(query):
    ytmusic_instance = get_ytmusic()
    results = ytmusic_instance.search(query, filter='songs', limit=15)
    parsed = []
    for item in results:
        artist = item.get('artists', [{'name': 'Bilinmeyen'}])[0]['name']
        thumbs = item.get('thumbnails', [])
        thumb_url = thumbs[-1]['url'] if thumbs else ''
        parsed.append({'title': item['title'], 'artist': artist, 'thumbnail': thumb_url, 'url': f"https://www.youtube.com/watch?v={item['videoId']}"})
    return parsed

@app.route('/api/search')
def api_search():
    q = request.args.get('q', '')
    if not q: return jsonify({'results': []})
    try: return jsonify({'results': cached_ytmusic_search(q)})
    except Exception as e: return jsonify({'results': []})

@app.route('/api/download_track', methods=['POST'])
def api_download_track():
    data = request.json
    url = data.get('original_url') or data.get('url')
    if data.get('url') == 'local': return jsonify({'success': True, 'local_filename': data.get('local_filename')})
    try:
        vid_id = url.split('v=')[-1][:11] if 'v=' in url else str(uuid.uuid4())[:11]
        filename = f"{vid_id}.m4a"
        filepath = os.path.join(DOWNLOAD_FOLDER, filename)
        if not os.path.exists(filepath):
            dl_opts = { 'format': 'bestaudio[ext=m4a]/bestaudio/best', 'outtmpl': filepath, 'quiet': True, 'no_warnings': True }
            with yt_dlp.YoutubeDL(dl_opts) as ydl: ydl.download([url])
        return jsonify({'success': True, 'local_filename': filename})
    except Exception as e: return jsonify({'success': False, 'error': str(e)})

@lru_cache(maxsize=20)
def cached_stream_url(url):
    info = ydl_engine.extract_info(url, download=False)
    return info['url']

@app.route('/api/play', methods=['POST'])
def api_play():
    data = request.json
    url = data.get('url')
    if url == 'local': return jsonify({'success': True, 'stream_url': f"/local_stream/{data['local_filename']}"})
    try: return jsonify({'success': True, 'stream_url': cached_stream_url(url)})
    except Exception as e: return jsonify({'success': False})

@app.route('/local_stream/<filename>')
def local_stream(filename): return send_from_directory(DOWNLOAD_FOLDER, filename)

@lru_cache(maxsize=50)
def cached_lyrics(artist, title):
    a = artist.replace(' - Topic', '').replace('VEVO', '').strip()
    t = re.sub(r'\(.*?\)|\[.*?\]', '', title).split(' ft.')[0].split(' feat.')[0].strip()
    search_query = f"{a} {t}".strip()
    display_title = f"{a} - {t}"
    try:
        url = f"https://lrclib.net/api/search?q={urllib.parse.quote(search_query)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4) as r:
            data = json.loads(r.read().decode('utf-8'))
            if data and len(data) > 0:
                lyrics = data[0].get('plainLyrics')
                if lyrics: return {'lyrics': lyrics, 'cleaned_title': display_title}
        return {'lyrics': f'"{display_title}" için sözler bulunamadı.', 'cleaned_title': display_title}
    except Exception as e: return {'lyrics': f'"{display_title}" için sözler bulunamadı.', 'cleaned_title': display_title}

@app.route('/api/lyrics')
def api_lyrics(): return jsonify(cached_lyrics(request.args.get('artist', ''), request.args.get('title', '')))

if __name__ == '__main__':
    # PORT değişkeni bulut sunucuları (Render, Heroku vb.) için hayatidir.
    port = int(os.environ.get("PORT", 5000))
    print(f"K Music Bulut Sunucusu Başlatılıyor... Port: {port}")
    serve(app, host='0.0.0.0', port=port, threads=12)