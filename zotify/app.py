from argparse import Namespace
from librespot.audio.decoders import AudioQuality
from tabulate import tabulate
from pathlib import Path

from zotify.album import download_album, download_artist_albums
from zotify.const import TRACK, NAME, ID, ARTIST, ARTISTS, ITEMS, TRACKS, EXPLICIT, ALBUM, ALBUMS, \
    OWNER, PLAYLIST, PLAYLISTS, DISPLAY_NAME
from zotify.playlist import get_playlist_info, download_from_user_playlist, download_playlist
from zotify.podcast import download_episode, download_show
from zotify.termoutput import Printer, PrintChannel
from zotify.track import download_track, get_saved_tracks, get_followed_artists
from zotify.utils import splash, split_sanitize_input, regex_input_for_urls
from zotify.zotify import Zotify

SEARCH_URL = 'https://api.spot'+'ify.com/v1/search'


def client(args: Namespace) -> None:
    """ Connects to download server to perform query's and get songs to download """
    Zotify(args)
    
    Printer.print(PrintChannel.SPLASH, splash())
    print("")
    
    quality_options = {
        'auto': AudioQuality.VERY_HIGH if Zotify.check_premium() else AudioQuality.HIGH,
        'normal': AudioQuality.NORMAL,
        'high': AudioQuality.HIGH,
        'very_high': AudioQuality.VERY_HIGH
    }
    Zotify.DOWNLOAD_QUALITY = quality_options[Zotify.CONFIG.get_download_quality()]
    
    if args.file_of_urls:
        urls = []
        filename = args.file_of_urls
        if Path(filename).exists():
            with open(filename, 'r', encoding='utf-8') as file:
                urls.extend([line.strip() for line in file.readlines()])
            
            download_from_urls(urls)
        
        else:
            Printer.print(PrintChannel.ERRORS, f'File {filename} not found.\n')
        return
    
    elif args.urls:
        if len(args.urls) > 0:
            if len(args.urls) == 1 and " " in args.urls[0]:
                args.urls = args.urls[0].split(' ')
            # Printer.print(PrintChannel.DOWNLOADS, f'###   DOWNLOADING URLS: {args.urls}')
            download_from_urls(args.urls)
        return
    
    elif args.playlist:
        download_from_user_playlist()
        return
    
    elif args.liked_songs:
        liked_songs = get_saved_tracks()
        
        pos = 3
        p_bar = Printer.progress(liked_songs, unit='songs', total=len(liked_songs), unit_scale=True, 
                                 disable=not Zotify.CONFIG.get_show_playlist_pbar(), pos=pos)
        wrapper_p_bars = [p_bar if Zotify.CONFIG.get_show_playlist_pbar() else pos]
        
        for song in p_bar:
            if not song[TRACK][NAME] or not song[TRACK][ID]:
                Printer.print(PrintChannel.SKIPS, '###   SKIPPING:  SONG DOES NOT EXIST ANYMORE   ###')
                Printer.print(PrintChannel.SKIPS, '\n\n')
            else:
                download_track('liked', song[TRACK][ID], wrapper_p_bars=wrapper_p_bars)
                p_bar.set_description(song[TRACK][NAME])
            for bar in wrapper_p_bars:
                if type(bar) != int: bar.refresh()
        return
    
    elif args.followed_artists:
        artists = get_followed_artists()
        pos = 7
        p_bar = Printer.progress(artists, unit='artists', total=len(artists), unit_scale=True, 
                                 disable=not Zotify.CONFIG.get_show_url_pbar(), pos=pos)
        wrapper_p_bars = [p_bar if Zotify.CONFIG.get_show_url_pbar() else pos]
        
        for artist in p_bar:
            download_artist_albums(artist[ID], wrapper_p_bars)
            p_bar.set_description(artist[NAME])
            for bar in wrapper_p_bars:
                if type(bar) != int: bar.refresh()
        return
    
    elif args.search:
        if args.search == ' ':
            search_text = ''
            while len(search_text) == 0:
                search_text = input('Enter search: ')
            search(search_text)
        else:
            if not download_from_urls([args.search]):
                search(args.search)
        return
    
    else:
        search_text = ''
        while len(search_text) == 0:
            search_text = input('Enter search: ')
        search(search_text)
        return


def download_from_urls(urls: list[str]) -> bool:
    """ Downloads from a list of urls """
    download = False
    
    pos = 7
    p_bar = Printer.progress(urls, unit='urls', total=len(urls), unit_scale=True, disable=not Zotify.CONFIG.get_show_url_pbar(), pos=pos)
    wrapper_p_bars = [p_bar if Zotify.CONFIG.get_show_url_pbar() else pos]
    for spotify_url in p_bar:
        track_id, album_id, playlist_id, episode_id, show_id, artist_id = regex_input_for_urls(spotify_url)
        
        if track_id is not None:
            download = True
            download_track('single', track_id, wrapper_p_bars=wrapper_p_bars)
        elif artist_id is not None:
            download = True
            download_artist_albums(artist_id, wrapper_p_bars)
        elif album_id is not None:
            download = True
            download_album(album_id, wrapper_p_bars)
        elif playlist_id is not None:
            download = True
            download_playlist({ID: playlist_id,
                               NAME: get_playlist_info(playlist_id)[0]},
                               wrapper_p_bars)
        elif episode_id is not None:
            download = True
            download_episode(episode_id, wrapper_p_bars)
        elif show_id is not None:
            download = True
            download_show(show_id, wrapper_p_bars)
        for bar in wrapper_p_bars:
            if type(bar) != int: bar.refresh()
    
    return download


def search(search_term) -> None:
    """ Searches download server's API for relevant data """
    params = {'limit': '10',
              'offset': '0',
              'q': search_term,
              'type': 'track,album,artist,playlist'}
    
    # Parse args
    splits = search_term.split()
    for split in splits:
        index = splits.index(split)

        if split[0] == '-' and len(split) > 1:
            if len(splits)-1 == index:
                raise IndexError('No parameters passed after option: {}\n'.
                                 format(split))

        if split == '-l' or split == '-limit':
            try:
                int(splits[index+1])
            except ValueError:
                raise ValueError('Parameter passed after {} option must be an integer.\n'.
                                 format(split))
            if int(splits[index+1]) > 50:
                raise ValueError('Invalid limit passed. Max is 50.\n')
            params['limit'] = splits[index+1]

        if split == '-t' or split == '-type':

            allowed_types = ['track', 'playlist', 'album', 'artist']
            passed_types = []
            for i in range(index+1, len(splits)):
                if splits[i][0] == '-':
                    break

                if splits[i] not in allowed_types:
                    raise ValueError('Parameters passed after {} option must be from this list:\n{}'.
                                     format(split, '\n'.join(allowed_types)))

                passed_types.append(splits[i])
            params['type'] = ','.join(passed_types)
    
    if len(params['type']) == 0:
        params['type'] = 'track,album,artist,playlist'
    
    # Clean search term
    search_term_list = []
    for split in splits:
        if split[0] == "-":
            break
        search_term_list.append(split)
    if not search_term_list:
        raise ValueError("Invalid query.")
    params["q"] = ' '.join(search_term_list)
    
    resp = Zotify.invoke_url_with_params(SEARCH_URL, **params)
    
    counter = 1
    search_results = []
    
    total_tracks = 0
    if TRACK in params['type'].split(','):
        tracks = resp[TRACKS][ITEMS]
        if len(tracks) > 0:
            print('###  TRACKS  ###')
            track_data = []
            for track in tracks:
                if track[EXPLICIT]:
                    explicit = '[E]'
                else:
                    explicit = ''

                track_data.append([counter, f'{track[NAME]} {explicit}',
                                  ','.join([artist[NAME] for artist in track[ARTISTS]])])
                search_results.append({
                    ID: track[ID],
                    NAME: track[NAME],
                    'type': TRACK,
                })
            
                counter += 1
            total_tracks = counter - 1
            print(tabulate(track_data, headers=[
                  'ID', 'Name', 'Artists'], tablefmt='pretty'))
            print('\n')
            del tracks
            del track_data
    
    total_albums = 0
    if ALBUM in params['type'].split(','):
        albums = resp[ALBUMS][ITEMS]
        if len(albums) > 0:
            print('###  ALBUMS  ###')
            album_data = []
            for album in albums:
                album_data.append([counter, album[NAME],
                                  ','.join([artist[NAME] for artist in album[ARTISTS]])])
                search_results.append({
                    ID: album[ID],
                    NAME: album[NAME],
                    'type': ALBUM,
                })
                
                counter += 1
            total_albums = counter - total_tracks - 1
            print(tabulate(album_data, headers=[
                  'ID', 'Album', 'Artists'], tablefmt='pretty'))
            print('\n')
            del albums
            del album_data
    
    total_artists = 0
    if ARTIST in params['type'].split(','):
        artists = resp[ARTISTS][ITEMS]
        if len(artists) > 0:
            print('###  ARTISTS  ###')
            artist_data = []
            for artist in artists:
                artist_data.append([counter, artist[NAME]])
                search_results.append({
                    ID: artist[ID],
                    NAME: artist[NAME],
                    'type': ARTIST,
                })
                counter += 1
            total_artists = counter - total_tracks - total_albums - 1
            print(tabulate(artist_data, headers=[
                  'ID', 'Name'], tablefmt='pretty'))
            print('\n')
            del artists
            del artist_data
    
    total_playlists = 0
    if PLAYLIST in params['type'].split(','):
        playlists = resp[PLAYLISTS][ITEMS]
        if len(playlists) > 0:
            print('###  PLAYLISTS  ###')
            playlist_data = []
            for playlist in playlists:
                playlist_data.append(
                    [counter, playlist[NAME], playlist[OWNER][DISPLAY_NAME]])
                search_results.append({
                    ID: playlist[ID],
                    NAME: playlist[NAME],
                    'type': PLAYLIST,
                })
                counter += 1
            total_playlists = counter - total_artists - total_tracks - total_albums - 1
            print(tabulate(playlist_data, headers=[
                  'ID', 'Name', 'Owner'], tablefmt='pretty'))
            print('\n')
            del playlists
            del playlist_data
    
    if total_tracks + total_albums + total_artists + total_playlists == 0:
        print('NO RESULTS FOUND - EXITING...')
        return
    
    print('> SELECT A DOWNLOAD OPTION BY ID')
    print('> SELECT A RANGE BY ADDING A DASH BETWEEN BOTH ID\'s')
    print('> OR PARTICULAR OPTIONS BY ADDING A COMMA BETWEEN ID\'s\n')
    raw_input = ''
    while len(raw_input) == 0:
        raw_input = str(input('ID(s): '))
    choices = split_sanitize_input(raw_input)
    
    pos = 7
    p_bar = Printer.progress(choices, unit='choices', total=len(choices), unit_scale=True, 
                                disable=not Zotify.CONFIG.get_show_url_pbar(), pos=pos)
    wrapper_p_bars = [p_bar if Zotify.CONFIG.get_show_url_pbar() else pos]
    
    for choice in p_bar:
        if choice <= len(search_results):
            selection = search_results[choice - 1]
            if selection['type'] == TRACK:
                download_track('single', selection[ID], wrapper_p_bars=wrapper_p_bars)
            elif selection['type'] == ALBUM:
                download_album(selection[ID], wrapper_p_bars)
            elif selection['type'] == ARTIST:
                download_artist_albums(selection[ID], wrapper_p_bars)
            else:
                download_playlist(selection, wrapper_p_bars)
        for bar in wrapper_p_bars:
            if type(bar) != int: bar.refresh()
