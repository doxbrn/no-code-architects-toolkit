from typing import Dict, Any
import os
import logging
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configurar o logger
logger = logging.getLogger(__name__)

# Carrega a chave da API do YouTube a partir da variável de ambiente
# Fallback para a chave fixa apenas se a variável de ambiente não estiver disponível
YOUTUBE_API_KEY = os.environ.get(
    "YOUTUBE_API_KEY", 
    "AIzaSyCd-47bEKqcnhLLEtP8kzCcDEzWYd195Eo"
)

def get_videos_by_channel_id(
    channel_id: str, 
    max_results: int = 500, 
    order_by: str = 'viewCount'
) -> Dict[str, Any]:
    """
    Obtém informações de vídeos de um canal do YouTube.

    Args:
        channel_id: O ID do canal do YouTube.
        max_results: Número máximo de vídeos para retornar (default 500).
        order_by: Critério de ordenação (default 'viewCount').

    Returns:
        Um dicionário contendo informações do canal e seus vídeos.
    """
    try:
        # Inicializar o serviço YouTube API
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        
        # Obter informações do canal
        channel_response = youtube.channels().list(
            part='snippet,statistics,brandingSettings',
            id=channel_id
        ).execute()
        
        if not channel_response.get('items'):
            logger.warning(f"Canal não encontrado: {channel_id}")
            return {
                "error": "Canal não encontrado",
                "channel_id": channel_id
            }
        
        channel_info = channel_response['items'][0]
        channel_data = {
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
            "videos": [],
            "total_videos_fetched": 0
        }
        
        # Buscar vídeos do canal
        videos = []
        next_page_token = None
        page_count = 0
        total_fetched = 0
        
        # O YouTube só permite 50 resultados por página,
        # então precisamos fazer várias requisições para chegar a 500 vídeos
        while total_fetched < max_results and page_count < 10:  # Limitar a 10 páginas (500 vídeos)
            # Sempre solicitar 50 para garantir que obtemos o máximo de resultados possível
            request_size = 50
            
            logger.debug(f"Buscando página {page_count + 1}, token: {next_page_token}")
            search_response = youtube.search().list(
                part='id',
                channelId=channel_id,
                maxResults=request_size,
                order=order_by,
                type='video',
                pageToken=next_page_token
            ).execute()
            
            page_count += 1
            
            video_ids = [item['id']['videoId'] 
                        for item in search_response.get('items', [])]
            
            if not video_ids:
                logger.debug(f"Nenhum vídeo encontrado na página {page_count}")
                break
            
            logger.debug(f"Encontrados {len(video_ids)} IDs de vídeos na página {page_count}")
            
            # Obter detalhes completos dos vídeos
            video_response = youtube.videos().list(
                part='snippet,contentDetails,statistics',
                id=','.join(video_ids)
            ).execute()
            
            page_videos = []
            for item in video_response.get('items', []):
                if total_fetched >= max_results:
                    break
                    
                video_data = {
                    "video_id": item['id'],
                    "title": item['snippet']['title'],
                    "description": item['snippet']['description'],
                    "published_at": item['snippet']['publishedAt'],
                    "thumbnail_url": item['snippet']['thumbnails']['high']['url'],
                    "duration": item['contentDetails']['duration'],
                    "view_count": int(item['statistics'].get('viewCount', 0)),
                    "like_count": int(item['statistics'].get('likeCount', 0)),
                    "dislike_count": int(item['statistics'].get('dislikeCount', 0)) 
                                  if 'dislikeCount' in item['statistics'] else 0,
                    "comment_count": int(item['statistics'].get('commentCount', 0)),
                    "tags": item['snippet'].get('tags', []),
                    "category_id": item['snippet']['categoryId'],
                }
                page_videos.append(video_data)
                total_fetched += 1
            
            # Adicionar os vídeos desta página à lista principal
            videos.extend(page_videos)
            logger.debug(f"Adicionados {len(page_videos)} vídeos. Total: {total_fetched}")
            
            # Verificar se há mais páginas
            next_page_token = search_response.get('nextPageToken')
            if not next_page_token:
                logger.debug("Não há mais páginas")
                break
        
        # Ordenar vídeos por contagem de visualizações (decrescente)
        videos.sort(key=lambda x: x['view_count'], reverse=True)
        
        channel_data['videos'] = videos
        channel_data['total_videos_fetched'] = len(videos)
        channel_data['total_pages_fetched'] = page_count
        
        logger.info(
            f"Obtidos {len(videos)} vídeos do canal {channel_id} em {page_count} páginas"
        )
        return channel_data
        
    except HttpError as e:
        error_details = {
            "error": f"Erro na API do YouTube: {str(e)}",
            "channel_id": channel_id
        }
        logger.error(f"Erro na API do YouTube: {str(e)}")
        return error_details
    except Exception as e:
        error_details = {
            "error": f"Erro ao processar dados: {str(e)}",
            "channel_id": channel_id
        }
        logger.error(f"Erro ao processar dados: {str(e)}")
        return error_details 