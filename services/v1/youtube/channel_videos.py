from typing import Dict, Any, List
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
    order_by: str = 'viewCount'
) -> Dict[str, Any]:
    """
    Obtém informações de vídeos de um canal do YouTube.
    Retorna dados do canal e uma lista de vídeos formatada para Airtable.

    Args:
        channel_id: O ID do canal do YouTube.
        max_results: Número máximo de vídeos para retornar (default 500).
        order_by: Critério de ordenação (default 'viewCount').

    Returns:
        Um dicionário contendo informações do canal e seus vídeos formatados para Airtable.
    """
    try:
        # Inicializar o serviço YouTube API
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        
        # Obter informações do canal
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
        # Basic channel data
        channel_data_response = {
            "channel_id": channel_id,
            "title": channel_info['snippet']['title'],
            "description": channel_info['snippet']['description'],
            "custom_url": channel_info['snippet'].get('customUrl', ''),
            "published_at": channel_info['snippet']['publishedAt'],
            "thumbnail_url": channel_info['snippet']['thumbnails']['high']['url'],
            "country": channel_info['snippet'].get('country', ''),
            "statistics": channel_info['statistics'],
            "banner_url": channel_info.get('brandingSettings', {})
                          .get('image', {})
                          .get('bannerExternalUrl', ''),
            "total_videos_fetched": 0,
            "total_pages_fetched": 0,
            "pagination_stop_reason": "",
            "airtable_videos": [] # Formatted for Airtable
        }
        
        videos_details_list = [] # To store detailed video objects before sorting
        next_page_token = None
        page_count = 0
        total_fetched_ids = 0
        
        # Max 10 pages for search to get top N by viewcount (500 videos)
        # The API might stop returning pages earlier for viewCount order on large channels
        max_pages_to_query = (max_results + 49) // 50 # Calculate pages needed, up to 10
        max_pages_to_query = min(max_pages_to_query, 10) 

        logger.info(f"Iniciando busca de vídeos para o canal {channel_id}. Max results: {max_results}, Order: {order_by}, Max pages: {max_pages_to_query}")

        while total_fetched_ids < max_results and page_count < max_pages_to_query:
            request_size = min(50, max_results - total_fetched_ids)
            if request_size <=0: # Should not happen if loop condition is correct
                break

            logger.debug(f"Buscando IDs - Página {page_count + 1}, maxResults: {request_size}, token: {next_page_token}")
            search_response = youtube.search().list(
                part='id',
                channelId=channel_id,
                maxResults=request_size, 
                order=order_by,
                type='video',
                pageToken=next_page_token
            ).execute()
            
            page_count += 1
            current_video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
            
            if not current_video_ids:
                logger.info(f"Nenhum ID de vídeo encontrado na página {page_count} da busca. Parando.")
                channel_data_response["pagination_stop_reason"] = f"API returned no video IDs on search page {page_count}."
                break
            
            logger.debug(f"Encontrados {len(current_video_ids)} IDs de vídeos na página de busca {page_count}.")
            
            # Get full details for these video IDs
            video_details_response = youtube.videos().list(
                part='snippet,contentDetails,statistics',
                id=','.join(current_video_ids)
            ).execute()
            
            for item in video_details_response.get('items', []):
                if total_fetched_ids >= max_results:
                    break
                videos_details_list.append(item)
                total_fetched_ids += 1
            
            logger.debug(f"Detalhes de {len(video_details_response.get('items', []))} vídeos obtidos. Total de IDs processados até agora: {total_fetched_ids}")

            next_page_token = search_response.get('nextPageToken')
            if not next_page_token:
                logger.info(f"Não há mais páginas de busca após a página {page_count}. Parando.")
                channel_data_response["pagination_stop_reason"] = f"API returned no next page token for search after page {page_count}."
                break
            if total_fetched_ids >= max_results:
                logger.info(f"Limite de {max_results} vídeos atingido ao buscar IDs. Parando.")
                channel_data_response["pagination_stop_reason"] = f"max_results ({max_results}) reached during ID fetching."
                break
        
        if not channel_data_response["pagination_stop_reason"] and total_fetched_ids < max_results:
             channel_data_response["pagination_stop_reason"] = "Loop finished (likely page cap or API limit for the query)."

        # Sort all fetched videos by view_count if that was the order
        # Note: The search API should have already ordered them, but we re-sort
        # in case we switch to playlistItems later or for absolute certainty.
        if order_by == 'viewCount':
            videos_details_list.sort(key=lambda v: int(v.get('statistics', {}).get('viewCount', 0)), reverse=True)

        # Now, format for Airtable
        airtable_formatted_videos = []
        for item in videos_details_list: # Iterate over the potentially sorted and limited list
            video_data_for_airtable = {
                "Video_ID": item['id'], # Primary Field in Airtable: fields.VideoID (fldbPdjT2QfwVFT6g)
                "Channel_ID_Ref": channel_id, # New field: Channel_ID_Ref (fldC0OaeIQsT2TCmS)
                "Title": item['snippet']['title'], # Airtable: fields.Title (fldGHKuZ3gFC8O20s)
                "Description": item['snippet']['description'], # Airtable: fields.Description (fldhHfOlvGCbfYaeD)
                "Published_At_Formatted": item['snippet']['publishedAt'], # New: Published_At_Formatted (dateTime). Store as ISO string.
                "Thumbnail_URL_Formatted": item['snippet']['thumbnails'].get('high', {}).get('url') or item['snippet']['thumbnails'].get('default', {}).get('url'), # New: Thumbnail_URL_Formatted (flduc8egch4qf3SBj)
                "Duration_Seconds": parse_iso8601_duration(item['contentDetails']['duration']), # Airtable: fields.DurationSeconds (fld0NYryE7Zjp6rDa)
                "View_Count": int(item.get('statistics', {}).get('viewCount', 0)), # Airtable: fields.ViewCount (fld0xre6jSfHbNGgs)
                "Like_Count": int(item.get('statistics', {}).get('likeCount', 0)), # New: Like_Count (fldXugCfOh6p6lTdc)
                "Comment_Count": int(item.get('statistics', {}).get('commentCount', 0)), # New: Comment_Count (fldd4dBX0FV3WNR1A)
                "Tags_List": ", ".join(item['snippet'].get('tags', [])), # New: Tags_List (fldZalcVklqW1Uxxy)
                "Category_ID_YT": item['snippet']['categoryId'], # New: Category_ID_YT (fldJMw0x1DM9LIX5b)
                # Existing Airtable fields not directly mapped from this specific video item:
                # fields.ChannelName (fldiu6lxgC7NbQXQf) - could be channel_info['snippet']['title']
                # fields.UploadDate (fldDqPsEeCsBVjbaX) - We're using Published_At_Formatted
            }
            airtable_formatted_videos.append(video_data_for_airtable)

        channel_data_response['airtable_videos'] = airtable_formatted_videos
        channel_data_response['total_videos_fetched'] = len(airtable_formatted_videos) # Actual number of videos in the list
        channel_data_response['total_pages_fetched'] = page_count
        
        logger.info(
            f"Finalizados: {len(airtable_formatted_videos)} vídeos formatados para Airtable do canal {channel_id} após {page_count} páginas de busca. Razão da parada: {channel_data_response['pagination_stop_reason']}"
        )
        return channel_data_response
        
    except HttpError as e:
        logger.error(f"Erro na API do YouTube para o canal {channel_id}: {str(e)}")
        return {
            "error": f"Erro na API do YouTube: {e.response.get('content', {}).decode() if e.response else str(e)}",
            "channel_id": channel_id,
            "airtable_videos": []
        }
    except Exception as e:
        logger.error(f"Erro geral ao processar dados para o canal {channel_id}: {str(e)}", exc_info=True)
        return {
            "error": f"Erro ao processar dados: {str(e)}",
            "channel_id": channel_id,
            "airtable_videos": []
        } 