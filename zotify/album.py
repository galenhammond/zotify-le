from zotify.const import ALBUM_URL, ARTIST_URL, ITEMS, ARTISTS, NAME, ID, DISC_NUMBER
from zotify.termoutput import Printer
from zotify.track import download_track
from zotify.utils import fix_filename
from zotify.zotify import Zotify


def get_album_info(album_id):
    """ Returns album info and tracklist"""
    
    (raw, resp) = Zotify.invoke_url(f'{ALBUM_URL}/{album_id}')
    
    album_name = fix_filename(resp[NAME])
    album_artist = resp[ARTISTS][0][NAME]
    
    songs = []
    offset = 0
    limit = 50
    
    while True:
        resp = Zotify.invoke_url_with_params(f'{ALBUM_URL}/{album_id}/tracks', limit=limit, offset=offset)
        offset += limit
        songs.extend(resp[ITEMS])
        if len(resp[ITEMS]) < limit:
            break
    
    total_discs = songs[-1][DISC_NUMBER]
    
    return album_name, album_artist, songs, total_discs


def get_artist_albums(artist_id):
    """ Returns artist's albums """
    (raw, resp) = Zotify.invoke_url(f'{ARTIST_URL}/{artist_id}/albums?include_groups=album%2Csingle')
    # Return a list each album's id
    album_ids = [resp[ITEMS][i][ID] for i in range(len(resp[ITEMS]))]
    # Recursive requests to get all albums including singles an EPs
    while resp['next'] is not None:
        (raw, resp) = Zotify.invoke_url(resp['next'])
        album_ids.extend([resp[ITEMS][i][ID] for i in range(len(resp[ITEMS]))])
    
    return album_ids


def download_artist_albums(artist, pbar_stack: list | None = None):
    """ Downloads albums of an artist """
    albums = get_artist_albums(artist)
    
    pos, pbar_stack = Printer.pbar_position_handler(5, pbar_stack)
    pbar = Printer.pbar(albums, unit='album', pos=pos,
                        disable=not Zotify.CONFIG.get_show_artist_pbar())
    pbar_stack.append(pbar)
    
    for album_id in pbar:
        download_album(album_id, pbar_stack)
        pbar.set_description(get_album_info(album_id)[0])
        Printer.refresh_all_pbars(pbar_stack)


def download_album(album, pbar_stack: list | None = None, M3U8_bypass: str | None = None):
    """ Downloads songs from an album """
    album_name, album_artist, tracks, total_discs = get_album_info(album)
    char_num = max({len(str(len(tracks))), 2})
    
    pos, pbar_stack = Printer.pbar_position_handler(3, pbar_stack)
    pbar = Printer.pbar(tracks, unit='song', pos=pos, 
                        disable=not Zotify.CONFIG.get_show_album_pbar())
    pbar_stack.append(pbar)
    
    for n, track in enumerate(pbar, 1):
        
        extra_keys={'album_num': str(n).zfill(char_num), 
                    'album_artist': album_artist, 
                    'album': album_name, 
                    'album_id': album,
                    'total_discs': total_discs}
        
        if M3U8_bypass is not None:
            extra_keys['M3U8_bypass'] = M3U8_bypass
        
        download_track('album', track[ID], 
                       extra_keys,
                       pbar_stack)
        pbar.set_description(track[NAME])
        Printer.refresh_all_pbars(pbar_stack)
