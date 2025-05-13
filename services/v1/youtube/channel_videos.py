from typing import Dict, Any
import os
import logging
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import isodate # For parsing ISO 8601 duration

# Configurar o logger
logger = logging.getLogger(__name__)

# Carrega a chave da API do YouTube a partir da variável de ambiente
# Fallback para a chave fixa apenas se a variável de ambiente não estiver disponível
YOUTUBE_API_KEY = os.environ.get(
    "YOUTUBE_API_KEY", 
    "AIzaSyCd-47bEKqcnhLLEtP8kzCcDEzWYd195Eo"
)

def parse_iso8601_duration(duration_str: str) -> int:
    """Converts ISO 8601 duration string to total seconds."""
    try:
        return int(isodate.parse_duration(duration_str).total_seconds())
    except Exception:
        logger.warning(f"Could not parse duration: {duration_str}. Returning 0.")
        return 0

def get_videos_by_channel_id(
    channel_id: str, 
    max_results: int = 500, 
    **kwargs # Aceita argumentos extras como order_by e os ignora
) -> Dict[str, Any]:
    """
    Obtém informações de vídeos de um canal do YouTube usando a playlist de uploads.
    Retorna dados do canal e uma lista de vídeos formatada para Airtable.

    Args:
        channel_id: O ID do canal do YouTube.
        max_results: Número máximo de vídeos para retornar (default 500).
        **kwargs: Permite que argumentos extras (como order_by da rota) sejam passados mas não usados.

    Returns:
        Um dicionário contendo informações do canal e seus vídeos formatados
        para Airtable.
    """
    # order_by = kwargs.get('order_by', 'viewCount') # Se precisasse usar, seria assim
    logger.info(f"Chamada a get_videos_by_channel_id para channel_id: {channel_id}, max_results: {max_results}. Argumentos extras ignorados: {kwargs}")
    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

        channel_response = youtube.channels().list(
            part='snippet,statistics,brandingSettings,contentDetails',
            id=channel_id
        ).execute()

        if not channel_response.get('items'):
            logger.warning(f"Canal não encontrado: {channel_id}")
            return {
                "error": "Canal não encontrado",
                "channel_id": channel_id,
                "airtable_videos": []
            }

        channel_info = channel_response['items'][0]
        uploads_playlist_id = channel_info.get('contentDetails', {}).get('relatedPlaylists', {}).get('uploads')

        if not uploads_playlist_id:
            logger.warning(f"Playlist de uploads não encontrada para o canal: {channel_id}")
            return {
                "error": "Playlist de uploads não encontrada para o canal",
                "channel_id": channel_id,
                "airtable_videos": []
            }
        
        logger.info(f"Playlist de uploads para {channel_id}: {uploads_playlist_id}")

        channel_data_response = {
            "channel_id": channel_id,
            "title": channel_info['snippet']['title'],
            "description": channel_info['snippet']['description'],
            "custom_url": channel_info['snippet'].get('customUrl', ''),
            "published_at": channel_info['snippet']['publishedAt'],
            "thumbnail_url":
                channel_info['snippet']['thumbnails']['high']['url'],
            "country": channel_info['snippet'].get('country', ''),
            "statistics": channel_info['statistics'],
            "banner_url": channel_info.get('brandingSettings', {})\
                          .get('image', {})\
                          .get('bannerExternalUrl', ''),
            "total_videos_fetched": 0,
            "total_pages_fetched": 0,
            "pagination_stop_reason": "",
            "airtable_videos": [] # Formatted for Airtable
        }

        collected_video_ids = []
        next_page_token = None
        page_count = 0
        total_fetched_ids_count = 0
        
        # Calculate the number of pages needed based on max_results (50 items per page)
        max_pages_to_query = (max_results + 49) // 50

        logger.info(
            f"Iniciando busca de vídeos (playlist: {uploads_playlist_id}) "
            f"para canal {channel_id}. Max results: {max_results}, "
            f"Max pages calculadas: {max_pages_to_query}"
        )

        while total_fetched_ids_count < max_results and page_count < max_pages_to_query:
            request_size = min(50, max_results - total_fetched_ids_count)
            if request_size <= 0:
                break

            logger.debug(
                f"Buscando playlistItems - Página {page_count + 1}, "
                f"maxResults: {request_size}, token: {next_page_token}"
            )
            playlist_items_response = youtube.playlistItems().list(
                part='contentDetails', # We only need contentDetails.videoId here
                playlistId=uploads_playlist_id,
                maxResults=request_size,
                pageToken=next_page_token
            ).execute()

            page_count += 1
            current_page_video_ids = [
                item['contentDetails']['videoId']
                for item in playlist_items_response.get('items', [])
                if item.get('contentDetails') and item['contentDetails'].get('videoId')
            ]

            if not current_page_video_ids:
                s_reason = f"API returned no video IDs from playlistItems on page {page_count}."
                logger.info(f"Nenhum ID de vídeo na página {page_count} da playlist. {s_reason}")
                channel_data_response["pagination_stop_reason"] = s_reason
                break
            
            collected_video_ids.extend(current_page_video_ids)
            total_fetched_ids_count = len(collected_video_ids)

            logger.debug(
                f"Encontrados {len(current_page_video_ids)} IDs de vídeos na "
                f"página {page_count} da playlist. Total de IDs coletados: {total_fetched_ids_count}."
            )

            next_page_token = playlist_items_response.get('nextPageToken')
            if not next_page_token:
                s_reason = f"API no next page token for playlistItems after page {page_count}."
                logger.info(f"Não há mais páginas na playlist após {page_count}. {s_reason}")
                channel_data_response["pagination_stop_reason"] = s_reason
                break
            if total_fetched_ids_count >= max_results:
                s_reason = f"max_results ({max_results}) reached during playlist ID fetching."
                logger.info(f"Limite de {max_results} vídeos atingido. {s_reason}")
                channel_data_response["pagination_stop_reason"] = s_reason
                break
        
        if not channel_data_response["pagination_stop_reason"] and \
           total_fetched_ids_count < max_results:
            channel_data_response["pagination_stop_reason"] = (
                "Loop finished (max pages reached or API limit for playlistItems)."
            )

        videos_details_list = []
        if collected_video_ids:
            # Fetch details for all collected video IDs in batches of 50
            for i in range(0, len(collected_video_ids), 50):
                batch_ids = collected_video_ids[i:i + 50]
                logger.debug(f"Buscando detalhes para lote de {len(batch_ids)} IDs de vídeo.")
                video_details_response = youtube.videos().list(
                    part='snippet,contentDetails,statistics,status',
                    id=','.join(batch_ids)
                ).execute()
                videos_details_list.extend(video_details_response.get('items', []))

        airtable_formatted_videos = []
        for item in videos_details_list:
            snippet = item.get('snippet', {})
            content_details = item.get('contentDetails', {})
            statistics = item.get('statistics', {})
            status = item.get('status', {})

            video_data_for_airtable = {
                "Video_ID": item.get('id'),
                "Channel_ID_Ref": channel_id,
                "Title": snippet.get('title'),
                "Description": snippet.get('description'),
                "Published_At_Formatted": snippet.get('publishedAt'),
                "Thumbnail_URL_Formatted":
                    snippet.get('thumbnails', {}).get('high', {})\
                    .get('url') or \
                    snippet.get('thumbnails', {}).get('default', {})\
                    .get('url'),
                "Duration_Seconds":
                    parse_iso8601_duration(content_details.get('duration', 'PT0S')),
                "View_Count":
                    int(statistics.get('viewCount', 0)),
                "Like_Count":
                    int(statistics.get('likeCount', 0)),
                "Comment_Count":
                    int(statistics.get('commentCount', 0)),
                "Tags_List":
                    ", ".join(snippet.get('tags', [])),
                "Category_ID_YT": snippet.get('categoryId'),
                
                # Novos campos do snippet
                "Channel_Title_In_Video": snippet.get('channelTitle'),
                "Live_Broadcast_Content": snippet.get('liveBroadcastContent'),
                "Default_Language": snippet.get('defaultLanguage'),
                "Default_Audio_Language": snippet.get('defaultAudioLanguage'),
                
                # Novos campos do contentDetails
                "Dimension": content_details.get('dimension'),
                "Definition": content_details.get('definition'),
                "Has_Caption": str(content_details.get('caption', 'false')).lower(), # Convertendo para string 'true'/'false'
                "Is_Licensed_Content": str(content_details.get('licensedContent', False)).lower(),
                "Projection": content_details.get('projection'),
                
                # Novos campos do status
                "Upload_Status": status.get('uploadStatus'),
                "Privacy_Status": status.get('privacyStatus'),
                "License": status.get('license'),
                "Is_Embeddable": str(status.get('embeddable', False)).lower(),
                "Are_Public_Stats_Viewable": str(status.get('publicStatsViewable', False)).lower(),
                "Made_For_Kids": str(status.get('madeForKids', False)).lower(),
                "Publish_At_Schedule": status.get('publishAt')
            }
            airtable_formatted_videos.append(video_data_for_airtable)

        channel_data_response['airtable_videos'] = airtable_formatted_videos
        channel_data_response['total_videos_fetched'] = len(airtable_formatted_videos)
        channel_data_response['total_pages_fetched'] = page_count

        logger.info(
            f"Finalizados: {len(airtable_formatted_videos)} vídeos formatados "
            f"para Airtable do canal {channel_id} após {page_count} páginas "
            f"da playlist. Razão da parada: "
            f"{channel_data_response['pagination_stop_reason']}"
        )
        return channel_data_response

    except HttpError as e:
        err_content = e.response.get('content', b'').decode() if e.response else str(e)
        logger.error(f"Erro na API do YouTube para o canal {channel_id}: {err_content}")
        return {
            "error": f"Erro na API do YouTube: {err_content}",
            "channel_id": channel_id,
            "airtable_videos": []
        }
    except Exception as e:
        logger.error(
            f"Erro geral ao processar dados para o canal {channel_id}: {str(e)}",
            exc_info=True
        )
        return {
            "error": f"Erro ao processar dados: {str(e)}",
            "channel_id": channel_id,
            "airtable_videos": []
        } 