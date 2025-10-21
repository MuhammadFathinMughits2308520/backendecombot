import cloudinary
import cloudinary.api
import cloudinary.utils
import os
from django.conf import settings

cloudinary.config(
    cloud_name = settings.CLOUD_NAME,
    api_key = settings.CLOUD_API_KEY,
    api_secret = settings.CLOUD_API_SECRET
)

def get_resources(prefix):
    """Ambil semua gambar dari folder Cloudinary tertentu."""
    return cloudinary.api.resources(
        type='upload',
        prefix=prefix,
        max_results=100
    )

def get_optimized_url(public_id, width=1920, quality='auto'):
    """
    Generate URL gambar yang sudah dioptimasi dengan transformasi Cloudinary.
    
    Args:
        public_id: ID public gambar di Cloudinary
        width: Lebar maksimal gambar (default: 1920px untuk desktop)
        quality: Kualitas gambar ('auto', 'auto:good', 'auto:best', atau 1-100)
    
    Returns:
        URL gambar yang sudah dioptimasi
    """
    return cloudinary.utils.cloudinary_url(
        public_id,
        width=width,
        quality=quality,
        fetch_format='auto',  # Otomatis pilih format terbaik (WebP untuk browser support)
        crop='limit',  # Tidak crop, hanya resize jika lebih besar
        secure=True,  # Gunakan HTTPS
        flags='progressive'  # Progressive loading untuk JPEG
    )[0]

def get_thumbnail_url(public_id, width=400, quality='auto:low'):
    """
    Generate URL thumbnail kecil untuk preview cepat.
    
    Args:
        public_id: ID public gambar di Cloudinary
        width: Lebar thumbnail (default: 400px)
        quality: Kualitas thumbnail
    
    Returns:
        URL thumbnail yang sangat ringan
    """
    return cloudinary.utils.cloudinary_url(
        public_id,
        width=width,
        quality=quality,
        fetch_format='auto',
        crop='limit',
        secure=True,
        flags='progressive',
        effect='blur:200'  # Optional: blur untuk LQIP (Low Quality Image Placeholder)
    )[0]

def get_optimized_resources(prefix, page_width=1920):
    """
    Ambil resources dengan URL yang sudah dioptimasi.
    
    Args:
        prefix: Folder path di Cloudinary
        page_width: Lebar halaman yang diinginkan
    
    Returns:
        Dict dengan list gambar dan metadata
    """
    resources = cloudinary.api.resources(
        type='upload',
        prefix=prefix,
        max_results=100
    )
    
    optimized_resources = []
    for resource in resources.get('resources', []):
        public_id = resource['public_id']
        
        # Generate URL optimized dan thumbnail
        optimized_url = get_optimized_url(public_id, width=page_width)
        thumbnail_url = get_thumbnail_url(public_id)
        
        optimized_resources.append({
            'public_id': public_id,
            'url': optimized_url,
            'thumbnail': thumbnail_url,
            'original_url': resource['secure_url'],
            'width': resource.get('width'),
            'height': resource.get('height'),
            'format': resource.get('format'),
            'bytes': resource.get('bytes')
        })
    
    return {
        'resources': optimized_resources,
        'total_count': len(optimized_resources)
    }

def generate_responsive_urls(public_id, breakpoints=[400, 800, 1200, 1920]):
    """
    Generate multiple URLs untuk responsive images di berbagai ukuran.
    
    Args:
        public_id: ID public gambar
        breakpoints: List ukuran width untuk responsive breakpoints
    
    Returns:
        Dict dengan URL untuk setiap breakpoint
    """
    urls = {}
    for width in breakpoints:
        urls[f'w{width}'] = get_optimized_url(public_id, width=width)
    
    return urls