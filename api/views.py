from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth.models import User
from .models import Feedback, UserComicProgress, ChatSession, ChatMessage, UserAnswer, UserProgress, ActivityProgress
from django.db import IntegrityError
from .serializers import UserSerializer, FeedbackSerializer, ChatMessageSerializer, UserAnswerSerializer
from rest_framework_simplejwt.views import TokenVerifyView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import permission_classes
from django.http import JsonResponse
from django.conf import settings
from .utils.cloudinary_utils import get_optimized_resources
from rest_framework import status
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from django.utils import timezone

# Import untuk chatbot
import sys
import os
import pandas as pd
import google.generativeai as genai
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from dotenv import load_dotenv
import logging

# Setup logging
logger = logging.getLogger(__name__)

# Load environment variables - PERBAIKAN: Load dari root directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(BASE_DIR, '.env')
load_dotenv(env_path)

# Configuration untuk chatbot - PATH DIPERBAIKI
CSV_PATH = os.path.join(BASE_DIR, "data/data.csv")
PERSIST_DIR = os.path.join(BASE_DIR, "chroma_db")

# PERBAIKAN: Debug environment variables
print(f"=== DEBUG: Current directory: {os.getcwd()} ===")
print(f"=== DEBUG: BASE_DIR: {BASE_DIR} ===")
print(f"=== DEBUG: CSV_PATH: {CSV_PATH} ===")
print(f"=== DEBUG: PERSIST_DIR: {PERSIST_DIR} ===")
print(f"=== DEBUG: .env path: {env_path} ===")
print(f"=== DEBUG: .env exists: {os.path.exists(env_path)} ===")

# Load API key dengan multiple fallbacks
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

# Debugging detail untuk API key
print(f"=== DEBUG: GEMINI_API_KEY loaded: {'YES' if API_KEY else 'NO'} ===")
if API_KEY:
    print(f"=== DEBUG: API Key length: {len(API_KEY)} ===")
    print(f"=== DEBUG: API Key starts with: {API_KEY[:10]}... ===")
    print(f"=== DEBUG: API Key ends with: ...{API_KEY[-4:]} ===")
else:
    print("=== DEBUG: API Key is EMPTY ===")
    # Tampilkan semua environment variables yang tersedia
    all_env_vars = {k: v for k, v in os.environ.items() if 'API' in k or 'KEY' in k}
    print(f"=== DEBUG: Available API/KEY env vars: {all_env_vars} ===")

MODEL = "gemini-2.0-flash-exp"  
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
TOP_K = 4

# Global variable for retriever
retriever = None

# Data struktur chatbot dari file JSON Anda
CHATBOT_FLOW = {
    "intro": {
        "id": "intro",
        "type": "bot_message",
        "character": "Aquano",
        "message": "Hallo, sudah siap untuk eksplorasi hari ini bersama Ecombot?",
        "image_url": "/assets/aquano-greeting.png",
        "image_source": "",
        "next_keywords": ["siap"]
    },
    "kimia_hijau": {
        "id": "kimia_hijau",
        "type": "bot_message",
        "character": "Aquano",
        "title": "Kimia Hijau (Green Chemistry)",
        "message": "Sebelum membahas tradisi Mapag Hujan, Ecombot akan mengulas terlebih dahulu materi kimia hijau atau green chemistry.\n\nKimia hijau (green chemistry) adalah pendekatan yang bertujuan menjaga lingkungan supaya tetap bersih dan aman. Intinya, semua proses dan produk kimia dibuat agar tidak menimbulkan limbah atau zat berbahaya bagi manusia dan alam. Ada 12 prinsip kimia hijau yang ditampilkan dalam gambar berikut ini!\n\nKimia hijau memiliki peranan penting dalam mewujudkan lingkungan agar tetap terjaga dan terhindar dari bencana alam, pemanasan global, dan terhindar dari paparan bahan kimia berbahaya.\n\nGimana? Apakah sudah paham dengan peran kimia hijau dan pentingnya kimia hijau? Jika belum, silahkan tanyakan dan diskusikan.",
        "image_url": "/assets/12-prinsip-kimia-hijau.png",
        "image_source": "sumber",
        "next_keywords": ["sudah", "forum diskusi"]
    },
    "pre_kegiatan": {
        "id": "pre_kegiatan",
        "type": "bot_message",
        "character": "Aquano",
        "message": "Luar Biasa, sekarang Ecombot akan memandu kamu mengeksplorasi tradisi Mapag Hujan dan menemukan bagaimana tradisi ini berhubungan dengan lingkungan serta prinsip kimia hijau.",
        "next_keywords": ["mulai kegiatan 1", "kembali ke kimia hijau", "forum diskusi"]
    },
    "kegiatan_1": {
        "id": "kegiatan_1",
        "type": "bot_message",
        "character": "Aquano",
        "title": "Kegiatan Eksplorasi 1: Masalah Sampah dan Banjir",
        "message": "Tahukah kamu? Musim hujan sering menimbulkan banjir di berbagai wilayah. Salah satu penyebab utama adalah menumpuknya sampah di sungai, selokan, dan gorong-gorong, sehingga aliran air menjadi tersumbat. Selain upaya pemerintah, masyarakat diminta berperan aktif dengan tidak membuang sampah sembarangan ke sungai maupun selokan. Kesadaran warga sangat penting karena meski pemerintah membersihkan, masalah banjir akan terus terjadi jika sampah tetap dibuang sembarangan.",
        "image_url": "/assets/masalah-banjir.png",
        "image_source": "",
        "question": {
            "id": "q_kegiatan_1",
            "text": "Masalah apa yang ditimbulkan oleh musim hujan sebagaimana dijelaskan dalam narasi di atas?",
            "type": "essay",
            "required": True,
            "storage_key": "answer:kegiatan_1",
            "max_length": 500
        },
        "next_keywords": ["pertanyaan", "mulai kegiatan 2", "kembali ke kegiatan 1", "forum diskusi"]
    },
    "kegiatan_2": {
        "id": "kegiatan_2",
        "type": "bot_message",
        "character": "Aquano",
        "title": "Kegiatan Eksplorasi 2: Tradisi Mapag Hujan",
        "message": "Di Jawa Barat khususnya di wilayah Bandung dan Subang mempunyai tradisi Mapag Hujan. Tahukah kamu? Tradisi ini menjadi sarana gotong royong masyarakat dalam membersihkan sungai, saluran air, dan lingkungan sekitar. Di Bandung, Mapag Hujan lebih difokuskan pada upaya mitigasi banjir dengan cara meningkatkan daya resapan air, mengelola sampah, serta melestarikan lingkungan. Kegiatan ini di dukung oleh pemerintah setempat melalui gerakan \"Maraton Bebersih Walungan dan Susukan\". Sementara itu di Subang, Mapag Hujan juga dilaksanakan sekaligus menampilkan berbagai pertunjukan seni tradisional, gotong royong membersihkan lingkungan, penanaman pohon, dan penghijauan sebagai wujud rasa syukur dan kepedulian terhadap alam.",
        "image_url": "/assets/tradisi-mapag-hujan.png",
        "image_source": "",
        "question": {
            "id": "q_kegiatan_2",
            "text": "Menurut kamu, bagaimana hubungan tradisi Mapag Hujan dengan masalah lingkungan sebelumnya?",
            "type": "essay",
            "required": True,
            "storage_key": "answer:kegiatan_2",
            "max_length": 500
        },
        "next_keywords": ["pertanyaan", "mulai kegiatan 3", "kembali ke kegiatan 2", "forum diskusi"]
    },
    "kegiatan_3": {
        "id": "kegiatan_3",
        "type": "bot_message",
        "character": "Aquano",
        "title": "Kegiatan Eksplorasi 3: Aspek Sains (Science)",
        "message": "Mapag Hujan memiliki hubungan erat dengan konsep-konsep ilmiah dalam sains lingkungan. Tradisi ini menunjukkan bagaimana keberadaan sampah di alam dan air hujan saling memengaruhi satu sama lain. Dari sudut pandang sains, Mapag Hujan dapat dipahami melalui kesadaran masyarakat akan pentingnya menjaga kebersihan sungai dan mengelola sampah sebelum musim hujan tiba. Jika sampah tidak dikelola dengan baik, kualitas air dan keseimbangan lingkungan bisa terganggu.\n\n1. Interaksi Air Hujan dengan Lingkungan\nAir hujan yang turun akan berinteraksi dengan material disekitarnya. Jika sungai dipenuhi sampah, air dapat melarutkan senyawa berbahaya seperti plastik, logam berat, dan limbah rumah tangga. Penumpukan sampah menyempitkan aliran air, menyebabkan sungai meluap saat hujan deras dan memicu banjir. Air banjir yang tercemar membawa zat kimia ke tanah dan air tanah, sehingga berisiko bagi kesehatan masyarakat.\n\n2. Pengaruh Sampah terhadap Kualitas Lingkungan\nSampah yang tidak dikelola dengan baik akan mencemari air, udara, dan tanah. Sampah organik membusuk menghasilkan gas seperti metana (CH4), amonia (NH3), H2S, dan CO2 yang mencemari udara. Limbah meningkatkan BOD dan COD, yang dapat menurunkan kadar oksigen terlarut, dan mengganggu kehidupan biota air. Air lindi dari sampah meresap ke tanah, membawa senyawa berbahaya dan logam berat. Mengubah struktur kimia tanah, menurunkan kesuburan, serta mencemari air tanah.",
        "image_url": "/assets/aspek-sains.png",
        "image_source": "",
        "question": {
            "id": "q_kegiatan_3",
            "text": "Diskusikan dengan kelompokmu!\n• Mengapa penumpukan sampah di dasar sungai dapat meningkatkan risiko banjir saat musim hujan?\n• Jika kamu menjadi bagian dari masyarakat yang tinggal di sekitar sungai, tindakan apa yang bisa kamu lakukan untuk mencegah dampak pencemaran lingkungan akibat sampah?",
            "type": "essay",
            "required": True,
            "storage_key": "answer:kegiatan_3",
            "max_length": 500
        },
        "next_keywords": ["pertanyaan", "mulai kegiatan 4", "kembali ke kegiatan 3", "forum diskusi"]
    },
    "kegiatan_4": {
        "id": "kegiatan_4",
        "type": "bot_message",
        "character": "Aquano",
        "title": "Kegiatan Eksplorasi 4: Aspek Teknologi (Technology)",
        "message": "Aspek ini berfokus pada penerapan teknologi untuk memecahkan permasalahan lingkungan akibat interaksi sampah dan hujan. Dalam tradisi Mapag Hujan, kearifan lokal masyarakat berkolaborasi dengan adaptasi teknologi yang didukung pemerintah setempat untuk menciptakan solusi ramah lingkungan. Melalui kolaborasi ini, masyarakat turut berperan dalam mengembangkan teknologi sederhana pengelolaan sampah secara berkelanjutan, salah satunya melalui pembuatan lubang resapan biopori.\n\nLubang biopori dibuat dengan kedalaman sekitar 1 meter dan diameter 10–30 cm untuk meningkatkan daya serap tanah terhadap air hujan serta mempercepat penguraian sampah organik menjadi kompos. Teknologi ramah lingkungan ini membantu menjaga ketersediaan air tanah dan mengurangi genangan di permukiman.\n\nDalam tradisi Mapag Hujan, penerapan biopori mencerminkan pemanfaatan teknologi sederhana berbasis sains untuk mitigasi banjir dan perbaikan kualitas tanah. Biopori menampung sampah organik agar terurai alami sekaligus meningkatkan kesuburan tanah.\n\nBerikut ini cara membuat biopori:\n1. Siapkan tanah di lokasi yang mudah menyerap air.\n2. Buat lubang tegak lurus sedalam ±1 meter, diameter 10–30 cm.\n3. Masukkan pipa PVC ke lubang agar tidak longsor.\n4. Isi dengan sampah organik seperti daun kering atau sisa sayuran.",
        "image_url": "/assets/biopori-diagram.png",
        "image_source": "",
        "questions": [
            {
                "id": "q_kegiatan_4_1",
                "text": "Apa hubungan solusi penggunaan teknologi lubang resapan biopori dengan prinsip kimia hijau!",
                "type": "discussion",
                "required": True,
                "storage_key": "answer:kegiatan_4_1",
                "max_length": 500
            },
            {
                "id": "q_kegiatan_4_2",
                "text": "Apakah ada solusi lain berbasis prinsip kimia hijau yang dapat kamu terapkan untuk mengatasi masalah pengelolaan sampah tersebut?",
                "type": "discussion",
                "required": True,
                "storage_key": "answer:kegiatan_4_2",
                "max_length": 500
            }
        ],
        "next_keywords": ["pertanyaan diskusi", "mulai kegiatan 5", "kembali ke kegiatan 4", "forum diskusi"]
    },
    "kegiatan_5": {
        "id": "kegiatan_5",
        "type": "bot_message",
        "character": "Aquano",
        "title": "Kegiatan Eksplorasi 5: Aspek Rekayasa (Engineering)",
        "message": "Aspek ini berhubungan dengan cara membuat solusi nyata lewat rekayasa atau teknik sederhana. Dalam kegiatan Mapag Hujan, masyarakat menerapkan sistem drainase alami dengan membuat lubang biopori. Lubang ini membantu air hujan meresap ke tanah dan mencegah banjir, sekaligus mengubah sampah organik jadi kompos yang bermanfaat bagi tanah.",
        "image_url": "/assets/engineering-biopori.png",
        "image_source": "",
        "question": {
            "id": "q_kegiatan_5",
            "text": "Rancanglah biopori versi kelompokmu dengan menggunakan bahan yang ada di sekitar seperti botol bekas, ember, kaleng! Perhatikan bahan yang digunakan, ukuran lubang, dan cara penempatannya di lingkungan rumah atau sekolah.",
            "type": "challenge",
            "required": True,
            "storage_key": "answer:kegiatan_5",
            "max_length": 1000,
            "allow_image_upload": True
        },
        "next_keywords": ["pertanyaan tantangan", "mulai kegiatan 6", "kembali ke kegiatan 5", "forum diskusi"]
    },
    "kegiatan_6": {
        "id": "kegiatan_6",
        "type": "bot_message",
        "character": "Aquano",
        "title": "Kegiatan Eksplorasi 6: Aspek Seni (Arts)",
        "message": "Mapag Hujan hadir dalam berbagai ekspresi budaya masyarakat. Di Subang, tradisi ini sering disertai dengan pembuatan poster maupun spanduk bertema lingkungan yang menekankan pentingnya menjaga kebersihan sungai. Selain itu, terdapat pula pertunjukan seni tradisional dan modern, seperti musik, tari, dan drama, yang dikemas dengan pesan moral tentang kelestarian lingkungan.",
        "image_url": "/assets/aspek-seni.png",
        "image_source": "",
        "question": {
            "id": "q_kegiatan_6",
            "text": "Ciptakan karya seni seperti gambar, poster, atau puisi yang bertema menjaga lingkungan berdasarkan prinsip kimia hijau!",
            "type": "creative",
            "required": True,
            "storage_key": "answer:kegiatan_6",
            "max_length": 2000,
            "allow_image_upload": True
        },
        "next_keywords": ["pertanyaan kreasi", "mulai kegiatan 7", "kembali ke kegiatan 6", "forum diskusi"]
    },
    "kegiatan_7": {
        "id": "kegiatan_7",
        "type": "bot_message",
        "character": "Aquano",
        "title": "Kegiatan Eksplorasi 7: Aspek Matematika (Mathematics)",
        "message": "Aspek ini digunakan untuk menganalisis efektivitas dukungan kegiatan Mapag Hujan dalam mendukung mitigasi banjir dan menjaga keseimbangan lingkungan. Analisis kuantitatif memberikan gambaran konkret mengenai hasil dan dampak dari kegiatan tersebut, sebagai contoh, volume genangan banjir Kota Bandung mengalami penurunan signifikan dari lebih dari 99.000 m³ pada tahun 2015 menjadi 36.000 m³ pada tahun 2023. Besar penurunan volume dapat dihitung sebagai:\n\nPersentase penurunan volume genangan = (99.000-36.000)/99.000 x 100% = 63,6%\n\nArtinya, terjadi penurunan volume genangan air sebesar 63,6% dalam kurun waktu delapan tahun, menunjukkan adanya dampak nyata dari program pengendalian banjir dan pembangunan infrastruktur hijau. Meskipun hasil ini tidak sepenuhnya disebabkan oleh tradisi Mapag Hujan, kegiatan tersebut memiliki peran penting dalam meningkatkan kesadaran dan partisipasi masyarakat terhadap pentingnya menjaga kebersihan lingkungan dan pengelolaan air. Kesadaran kolektif inilah yang menjadi langkah awal dalam mendukung keberhasilan program mitigasi banjir secara berkelanjutan.",
        "image_url": "/assets/data-banjir-bandung.png",
        "image_source": "",
        "questions": [
            {
                "id": "q_kegiatan_7_1",
                "text": "Menurutmu, apakah tradisi Mapag Hujan dapat terus dilestarikan untuk membantu mengurangi masalah lingkungan di masa depan? Jelaskan pendapatmu?",
                "type": "reflective",
                "required": True,
                "storage_key": "answer:kegiatan_7_1",
                "max_length": 500
            },
            {
                "id": "q_kegiatan_7_2",
                "text": "Bagaimana menurutmu, apakah adaptasi Tradisi Mapag Hujan sejalan dengan prinsip kimia hijau? Jelaskan",
                "type": "reflective",
                "required": True,
                "storage_key": "answer:kegiatan_7_2",
                "max_length": 500
            }
        ],
        "next_keywords": ["pertanyaan reflektif", "kembali ke kegiatan 6", "forum diskusi", "selesai"]
    },
    "completion": {
        "id": "completion",
        "type": "bot_message",
        "character": "Aquano",
        "title": "Eksplorasi Selesai",
        "message": "Selamat! kamu telah menyelesaikan seluruh eksplorasi ini.\n\nDengan menyelesaikan kegiatan ini, kamu telah belajar tentang tradisi Mapag Hujan, bagaimana tradisi ini membantu mitigasi banjir, mengelola sampah, dan menjaga keseimbangan lingkungan. Selain itu, kamu juga memahami keterkaitan tradisi lokal dengan prinsip kimia hijau, serta pentingnya literasi lingkungan dalam kehidupan sehari-hari. Gunakan pengetahuan ini untuk membuat keputusan yang lebih bijak terhadap lingkungan di rumah, sekolah, atau lingkungan sekitar.",
        "next_keywords": ["forum diskusi", "kembali ke menu"]
    }
}

# Navigation rules berdasarkan file JSON Anda
NAVIGATION_RULES = {
    "intro": {
        "siap": "kimia_hijau"
    },
    "kimia_hijau": {
        "sudah": "pre_kegiatan",
        "forum diskusi": "forum_diskusi"
    },
    "pre_kegiatan": {
        "mulai kegiatan 1": "kegiatan_1",
        "kembali ke kimia hijau": "kimia_hijau",
        "forum diskusi": "forum_diskusi"
    },
    "kegiatan_1": {
        "pertanyaan": "kegiatan_1_question",
        "mulai kegiatan 2": "kegiatan_2",
        "kembali ke kegiatan 1": "kegiatan_1",
        "forum diskusi": "forum_diskusi"
    },
    "kegiatan_2": {
        "pertanyaan": "kegiatan_2_question",
        "mulai kegiatan 3": "kegiatan_3",
        "kembali ke kegiatan 2": "kegiatan_2",
        "forum diskusi": "forum_diskusi"
    },
    "kegiatan_3": {
        "pertanyaan": "kegiatan_3_question",
        "mulai kegiatan 4": "kegiatan_4",
        "kembali ke kegiatan 3": "kegiatan_3",
        "forum diskusi": "forum_diskusi"
    },
    "kegiatan_4": {
        "pertanyaan diskusi": "kegiatan_4_discussion",
        "mulai kegiatan 5": "kegiatan_5",
        "kembali ke kegiatan 4": "kegiatan_4",
        "forum diskusi": "forum_diskusi"
    },
    "kegiatan_5": {
        "pertanyaan tantangan": "kegiatan_5_challenge",
        "mulai kegiatan 6": "kegiatan_6",
        "kembali ke kegiatan 5": "kegiatan_5",
        "forum diskusi": "forum_diskusi"
    },
    "kegiatan_6": {
        "pertanyaan kreasi": "kegiatan_6_creative",
        "mulai kegiatan 7": "kegiatan_7",
        "kembali ke kegiatan 6": "kegiatan_6",
        "forum diskusi": "forum_diskusi"
    },
    "kegiatan_7": {
        "pertanyaan reflektif": "kegiatan_7_reflective",
        "kembali ke kegiatan 6": "kegiatan_6",
        "forum diskusi": "forum_diskusi",
        "selesai": "completion"
    },
    "completion": {
        "forum diskusi": "forum_diskusi",
        "kembali ke menu": "intro"
    },
    "forum_diskusi": {
        "kembali ke kimia hijau": "kimia_hijau",
        "kembali ke kegiatan 1": "kegiatan_1",
        "kembali ke kegiatan 2": "kegiatan_2",
        "kembali ke kegiatan 3": "kegiatan_3",
        "kembali ke kegiatan 4": "kegiatan_4",
        "kembali ke kegiatan 5": "kegiatan_5",
        "kembali ke kegiatan 6": "kegiatan_6",
        "kembali ke kegiatan 7": "kegiatan_7",
        "kembali ke kegiatan akhir": "completion"
    }
}

# ===== FUNGSI RAG SYSTEM YANG DIPERBAIKI =====

def create_fallback_retriever():
    """Create a fallback retriever with basic knowledge"""
    try:
        logger.info("Creating fallback retriever...")
        fallback_docs = [
            Document(
                page_content="""
                Topik: Kimia Hijau (Green Chemistry)
                Pertanyaan: Apa itu Kimia Hijau?
                Jawaban: Kimia Hijau adalah pendekatan dalam ilmu kimia yang bertujuan merancang produk dan proses kimia yang mengurangi atau menghilangkan penggunaan dan pembentukan zat berbahaya. Ada 12 prinsip kimia hijau yang meliputi pencegahan limbah, atom economy, desain bahan kimia yang lebih aman, dan penggunaan energi yang efisien.
                Context: Pendidikan kimia berkelanjutan
                Keywords: kimia hijau, green chemistry, lingkungan, berkelanjutan
                Related topics: prinsip kimia hijau, lingkungan berkelanjutan
                """,
                metadata={"topic": "Kimia Hijau", "category": "education"}
            ),
            Document(
                page_content="""
                Topik: Tradisi Mapag Hujan
                Pertanyaan: Apa itu tradisi Mapag Hujan?
                Jawaban: Mapag Hujan adalah tradisi masyarakat Jawa Barat khususnya di Bandung dan Subang yang bertujuan menyambut musim hujan dengan membersihkan lingkungan, sungai, dan saluran air. Tradisi ini merupakan bentuk kearifan lokal dalam mitigasi banjir dan pelestarian lingkungan.
                Context: Kearifan lokal dan lingkungan
                Keywords: mapag hujan, tradisi, jawa barat, lingkungan, banjir
                Related topics: budaya lokal, konservasi air, mitigasi banjir
                """,
                metadata={"topic": "Mapag Hujan", "category": "culture"}
            ),
            Document(
                page_content="""
                Topik: Prinsip Kimia Hijau
                Pertanyaan: Apa saja prinsip-prinsip kimia hijau?
                Jawaban: 12 Prinsip Kimia Hijau meliputi: 1. Pencegahan limbah, 2. Atom economy, 3. Sintesis bahan kimia yang kurang berbahaya, 4. Desain bahan kimia yang lebih aman, 5. Pelarut dan bahan pembantu yang lebih aman, 6. Efisiensi energi, 7. Penggunaan bahan baku terbarukan, 8. Mengurangi turunan, 9. Katalisis, 10. Desain untuk degradasi, 11. Analisis real-time untuk pencegahan polusi, 12. Kimia yang secara inherent lebih aman untuk pencegahan kecelakaan.
                Context: Pendidikan kimia
                Keywords: prinsip kimia hijau, 12 prinsip, green chemistry principles
                Related topics: kimia berkelanjutan, pendidikan lingkungan
                """,
                metadata={"topic": "Prinsip Kimia Hijau", "category": "education"}
            ),
            Document(
                page_content="""
                Topik: Mitigasi Banjir
                Pertanyaan: Bagaimana cara mitigasi banjir?
                Jawaban: Mitigasi banjir dapat dilakukan melalui: membersihkan sungai dan saluran air, membuat biopori untuk meningkatkan resapan air, menanam pohon, tidak membuang sampah sembarangan, dan partisipasi masyarakat dalam menjaga lingkungan.
                Context: Konservasi lingkungan
                Keywords: mitigasi banjir, biopori, konservasi air, lingkungan
                Related topics: pencegahan banjir, pelestarian lingkungan
                """,
                metadata={"topic": "Mitigasi Banjir", "category": "environment"}
            )
        ]
        
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        vectorstore = Chroma.from_documents(fallback_docs, embeddings)
        retriever = vectorstore.as_retriever(search_kwargs={"k": TOP_K})
        logger.info("[+] Fallback retriever created successfully")
        return retriever
    except Exception as e:
        logger.error(f"Error creating fallback retriever: {e}")
        return None

def initialize_rag_system():
    """Initialize the RAG system with enhanced error handling"""
    global retriever
    try:
        # Debug info
        logger.info("=== STARTING RAG INITIALIZATION ===")
        
        # Check if persisted vectorstore exists
        if os.path.exists(PERSIST_DIR) and os.listdir(PERSIST_DIR):
            logger.info("Found existing vectorstore, loading...")
            try:
                embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
                vectorstore = Chroma(persist_directory=PERSIST_DIR, embedding_function=embeddings)
                retriever = vectorstore.as_retriever(search_kwargs={"k": TOP_K})
                logger.info("[+] Loaded existing vectorstore successfully")
                return retriever
            except Exception as e:
                logger.warning(f"Failed to load existing vectorstore: {e}. Rebuilding...")
        
        # Check if CSV file exists
        if not os.path.exists(CSV_PATH):
            logger.error(f"CSV file not found: {CSV_PATH}")
            # Create data directory if it doesn't exist
            os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
            # Create fallback CSV file
            create_fallback_csv()
            logger.info("Created fallback CSV file")
        
        # Load and process CSV data
        logger.info("Loading CSV data...")
        df = pd.read_csv(CSV_PATH, dtype=str, on_bad_lines="skip").fillna("")
        documents = []

        for _, row in df.iterrows():
            content_parts = []
            if "topic" in df.columns and pd.notna(row.get('topic')): 
                content_parts.append(f"Topik: {row['topic']}")
            if "question" in df.columns and pd.notna(row.get('question')): 
                content_parts.append(f"Pertanyaan: {row['question']}")
            if "answer" in df.columns and pd.notna(row.get('answer')): 
                content_parts.append(f"Jawaban: {row['answer']}")
            if "context" in df.columns and pd.notna(row.get('context')): 
                content_parts.append(f"Context: {row['context']}")
            if "keywords" in df.columns and pd.notna(row.get('keywords')): 
                content_parts.append(f"Keywords: {row['keywords']}")
            if "related_topics" in df.columns and pd.notna(row.get('related_topics')): 
                content_parts.append(f"Related topics: {row['related_topics']}")
            
            content = "\n\n".join(content_parts).strip()
            if content:  # Only add if content is not empty
                metadata = {col: row[col] for col in df.columns if col in ["id", "category", "topic"] and pd.notna(row.get(col))}
                documents.append(Document(page_content=content, metadata=metadata))

        logger.info(f"[+] Loaded {len(documents)} documents")

        if not documents:
            logger.warning("No documents found in CSV, using fallback data")
            return create_fallback_retriever()

        # Split text into chunks
        splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        chunks = splitter.split_documents(documents)
        logger.info(f"[+] Split into {len(chunks)} chunks")

        # Create directory if it doesn't exist
        os.makedirs(PERSIST_DIR, exist_ok=True)

        # Embedding & Vectorstore
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        vectorstore = Chroma.from_documents(
            chunks, 
            embeddings, 
            persist_directory=PERSIST_DIR
        )
        vectorstore.persist()
        retriever = vectorstore.as_retriever(search_kwargs={"k": TOP_K})
        logger.info("[+] Vectorstore created and persisted successfully")
        
        return retriever
        
    except Exception as e:
        logger.error(f"Error initializing RAG system: {e}")
        logger.info("Using fallback retriever")
        return create_fallback_retriever()

def create_fallback_csv():
    """Create a fallback CSV file with basic data"""
    try:
        import csv
        
        fallback_data = [
            {
                'id': '1', 
                'topic': 'Kimia Hijau', 
                'question': 'Apa itu Kimia Hijau?', 
                'answer': 'Kimia Hijau adalah pendekatan dalam ilmu kimia yang bertujuan merancang produk dan proses kimia yang mengurangi atau menghilangkan penggunaan dan pembentukan zat berbahaya.',
                'context': 'Pendidikan kimia berkelanjutan',
                'keywords': 'kimia hijau, green chemistry, lingkungan, berkelanjutan',
                'related_topics': 'prinsip kimia hijau, lingkungan berkelanjutan'
            },
            {
                'id': '2', 
                'topic': 'Mapag Hujan', 
                'question': 'Apa itu tradisi Mapag Hujan?', 
                'answer': 'Mapag Hujan adalah tradisi masyarakat Jawa Barat khususnya di Bandung dan Subang yang bertujuan menyambut musim hujan dengan membersihkan lingkungan, sungai, dan saluran air.',
                'context': 'Kearifan lokal dan lingkungan',
                'keywords': 'mapag hujan, tradisi, jawa barat, lingkungan, banjir',
                'related_topics': 'budaya lokal, konservasi air, mitigasi banjir'
            },
            {
                'id': '3', 
                'topic': 'Prinsip Kimia Hijau', 
                'question': 'Apa saja prinsip-prinsip kimia hijau?', 
                'answer': '12 Prinsip Kimia Hijau meliputi: pencegahan limbah, atom economy, sintesis bahan kimia yang kurang berbahaya, desain bahan kimia yang lebih aman, pelarut dan bahan pembantu yang lebih aman, efisiensi energi, penggunaan bahan baku terbarukan, mengurangi turunan, katalisis, desain untuk degradasi, analisis real-time untuk pencegahan polusi, kimia yang secara inherent lebih aman.',
                'context': 'Pendidikan kimia',
                'keywords': 'prinsip kimia hijau, 12 prinsip, green chemistry principles',
                'related_topics': 'kimia berkelanjutan, pendidikan lingkungan'
            }
        ]
        
        with open(CSV_PATH, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['id', 'topic', 'question', 'answer', 'context', 'keywords', 'related_topics']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(fallback_data)
            
        logger.info(f"Fallback CSV created at: {CSV_PATH}")
    except Exception as e:
        logger.error(f"Error creating fallback CSV: {e}")

# Initialize RAG system dengan error handling
try:
    logger.info("Attempting to initialize RAG system...")
    rag_status = initialize_rag_system()
    if rag_status:
        logger.info("✅ RAG system initialized successfully")
    else:
        logger.warning("⚠️ RAG system initialization failed, using fallback")
except Exception as e:
    logger.error(f"❌ RAG system initialization error: {e}")

# ===== VIEWS PERTAMA (EXISTING) =====
@api_view(['POST'])
def register(request):
    try:
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            username = serializer.validated_data['username']
            password = serializer.validated_data['password']

            user = User(username=username, is_active=True)
            user.set_password(password)
            user.save()

            return Response({'message': 'User registered successfully!'})
        return Response(serializer.errors, status=400)
    except IntegrityError:
        return Response({'error': 'Username already exists'}, status=400)

from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import permission_classes

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ecombot(request):
    return Response({
        "message": f"Halo, {request.user.username}! Ini halaman profil kamu."
    })


from django.http import JsonResponse
from django.conf import settings
from .utils.cloudinary_utils import get_optimized_resources

def manifest(request, comic_slug, episode_slug):
    prefix = f"comics/{comic_slug}/{episode_slug}"
    
    # Gunakan fungsi optimized
    result = get_optimized_resources(prefix, page_width=1920)
    
    manifest = {
        'title': f"{comic_slug} - Episode {episode_slug}",
        'pages': [
            {
                'index': idx,
                'url': img['url'],  # URL sudah optimized!
                'thumbnail': img['thumbnail'],  # Untuk preview
                'alt': f"Page {idx + 1}"
            }
            for idx, img in enumerate(result['resources'])
        ]
    }
    
    return JsonResponse(manifest)


from .models import UserComicProgress

from rest_framework import status

REQUIRED_PAGE_THRESHOLD = 3  # indeks (0-based), berarti halaman ke-4

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def comic_progress(request):
    user = request.user

    if request.method == 'GET':
        comic = request.query_params.get('comic')
        episode = request.query_params.get('episode')
        
        try:
            progress = UserComicProgress.objects.get(
                user=user, 
                comic_slug=comic, 
                episode_slug=episode
            )
            
            # Jika finish, allowed_page = unlimited (gunakan angka besar)
            # Jika belum finish, allowed_page = 2 (index 0-2, yaitu halaman 1-3)
            allowed_page = 999 if progress.finish else 2
            
            return Response({
                "finish": progress.finish,
                "allowed_page": allowed_page,
                "last_page": progress.last_page
            })
        except UserComicProgress.DoesNotExist:
            # User baru, belum pernah baca komik ini
            return Response({
                "finish": False, 
                "allowed_page": 2,  # hanya bisa sampai halaman ke-3 (index 2)
                "last_page": 0
            })

    # --- POST: update posisi halaman ---
    if request.method == 'POST':
        comic = request.data.get('comic')
        episode = request.data.get('episode')
        try:
            last_page = int(request.data.get('last_page', 0))
        except (TypeError, ValueError):
            return Response({"error": "Invalid last_page"}, status=status.HTTP_400_BAD_REQUEST)

        progress, created = UserComicProgress.objects.get_or_create(
            user=user,
            comic_slug=comic,
            episode_slug=episode,
            defaults={"last_page": 0, "finish": False}
        )

        # Update last_page hanya jika lebih besar (jangan turunkan progress)
        if last_page > progress.last_page:
            progress.last_page = last_page

        progress.save()
        
        # Kembalikan allowed_page yang benar
        allowed_page = 999 if progress.finish else 2

        return Response({
            "saved": True,
            "finish": progress.finish,
            "allowed_page": allowed_page,
            "last_page": progress.last_page
        })



from rest_framework import status

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def comic_mark_finish(request):
    """
    POST /api/comic-progress/finish/
    body: { "comic": "...", "episode": "...", "last_page": 3, "complete": true }
    Jika client mengirim "complete": true -> set finish=True langsung untuk user itu.
    """
    user = request.user
    comic = request.data.get("comic")
    episode = request.data.get("episode")
    last_page_body = request.data.get("last_page")
    complete_flag = bool(request.data.get("complete", False))  # <-- new flag
    force = bool(request.data.get("force", False))  # tetap ada untuk admin override if needed

    if not comic or not episode:
        return Response({"error": "Missing comic or episode"}, status=status.HTTP_400_BAD_REQUEST)

    progress, _ = UserComicProgress.objects.get_or_create(
        user=user,
        comic_slug=comic,
        episode_slug=episode,
        defaults={"last_page": 0, "finish": False}
    )

    # update last_page jika dikirim
    if last_page_body is not None:
        try:
            lp = int(last_page_body)
            if lp > progress.last_page:
                progress.last_page = lp
        except (ValueError, TypeError):
            return Response({"error": "Invalid last_page"}, status=status.HTTP_400_BAD_REQUEST)

    # Jika client menandai 'complete' -> langsung set finish True
    if complete_flag:
        progress.finish = True
        progress.save()
        return Response({"saved": True, "finish": True, "message": "Marked as complete by user"})


    # Force (untuk staff/admin)
    if force and user.is_staff:
        progress.finish = True
        progress.save()
        return Response({"saved": True, "finish": True})

    # Default behavior: require threshold
    effective_last = progress.last_page
    if last_page_body is not None:
        try:
            effective_last = max(effective_last, int(last_page_body))
        except:
            pass

    if effective_last >= REQUIRED_PAGE_THRESHOLD:
        progress.finish = True
        progress.save()
        return Response({"saved": True, "finish": True})
    else:
        return Response(
            {
                "saved": False,
                "finish": False,
                "message": "Belum mencapai batas eksplorasi. Selesaikan explorasi terlebih dahulu.",
                "required_page": REQUIRED_PAGE_THRESHOLD,
                "current_last_page": effective_last
            },
            status=status.HTTP_403_FORBIDDEN
        )

@api_view(['POST', 'GET'])
@permission_classes([AllowAny])  # ✅ tidak perlu login
def feedback_view(request):
    if request.method == 'POST':
        serializer = FeedbackSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Feedback berhasil dikirim!'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'GET':
        feedbacks = Feedback.objects.all().order_by('-tanggal')
        serializer = FeedbackSerializer(feedbacks, many=True)
        return Response(serializer.data)

from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response({"detail": "Refresh token tidak diberikan"}, status=status.HTTP_400_BAD_REQUEST)

            token = RefreshToken(refresh_token)
            token.blacklist()  # blacklist token agar tidak bisa dipakai lagi
            return Response({"detail": "Logout berhasil"}, status=status.HTTP_205_RESET_CONTENT)
        except TokenError:
            return Response({"detail": "Token tidak valid atau sudah kadaluarsa"}, status=status.HTTP_400_BAD_REQUEST)












# ===== FUNGSI GEMINI YANG DIPERBAIKI =====

def query_gemini(prompt):
    """Query Gemini API dengan enhanced error handling"""
    try:
        # Debug API key sebelum digunakan
        print(f"=== DEBUG query_gemini: API_KEY available: {bool(API_KEY)} ===")
        
        if not API_KEY:
            error_msg = "API key tidak ditemukan. Pastikan GEMINI_API_KEY sudah di-set di file .env"
            logger.error(error_msg)
            return f"Maaf, {error_msg}. Silakan hubungi administrator."

        # Validasi format API key
        if not API_KEY.startswith('AIza'):
            error_msg = f"Format API key tidak valid. Harus dimulai dengan 'AIza'. Dapatkan: {API_KEY[:10]}..."
            logger.error(error_msg)
            return f"Maaf, {error_msg}. Silakan periksa kunci API Gemini Anda."

        # Initialize client dengan cara yang benar
        try:
            # PERBAIKAN: Konfigurasi yang benar untuk google-generativeai
            genai.configure(api_key=API_KEY)
            print("=== DEBUG: Gemini client configured successfully ===")
        except Exception as client_error:
            logger.error(f"Error configuring Gemini client: {client_error}")
            return f"Maaf, gagal mengkonfigurasi klien Gemini: {str(client_error)}"

        # Generate content
        try:
            print("=== DEBUG: Sending request to Gemini API ===")
            
            # PERBAIKAN: Gunakan model yang benar
            model = genai.GenerativeModel(MODEL)
            response = model.generate_content(prompt)
            
            print("=== DEBUG: Received response from Gemini API ===")
            
            if hasattr(response, 'text'):
                return response.text
            else:
                logger.error(f"Unexpected response format: {response}")
                return "Maaf, format respons dari API tidak dikenali."
                
        except Exception as gen_error:
            logger.error(f"Error generating content: {gen_error}")
            error_str = str(gen_error)
            
            if "quota" in error_str.lower():
                return "Maaf, kuota API telah habis. Silakan coba lagi nanti atau hubungi administrator."
            elif "permission" in error_str.lower() or "invalid" in error_str.lower():
                return "Maaf, API key tidak valid atau tidak memiliki izin. Silakan periksa kunci API Anda."
            elif "network" in error_str.lower() or "connection" in error_str.lower():
                return "Maaf, terjadi masalah koneksi. Silakan periksa koneksi internet Anda dan coba lagi."
            elif "safety" in error_str.lower():
                return "Maaf, pertanyaan Anda ditolak oleh filter keamanan. Silakan coba dengan pertanyaan lain."
            else:
                return f"Maaf, terjadi kesalahan saat memproses pertanyaan: {error_str}"
        
    except Exception as e:
        logger.error(f"Unexpected error in query_gemini: {e}")
        return f"Maaf, terjadi kesalahan tak terduga: {str(e)}. Silakan coba lagi."

# ===== ENDPOINT RAG YANG DIPERBAIKI =====

@api_view(['POST'])
@permission_classes([AllowAny])
def ask_question(request):
    """Handle question asking with RAG system - ENHANCED VERSION"""
    try:
        question = request.data.get('question', '').strip()
        
        if not question:
            return Response(
                {"answer": "Silakan ajukan pertanyaan yang lebih spesifik."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        logger.info(f"Processing question: '{question}'")
        
        # Get relevant documents from RAG system
        context = ""
        relevant_docs = []
        
        if retriever:
            try:
                docs = retriever.get_relevant_documents(question)
                context = "\n\n".join([d.page_content for d in docs])
                relevant_docs = docs
                logger.info(f"Retrieved {len(docs)} documents for question")
            except Exception as e:
                logger.error(f"Error retrieving documents: {e}")
                context = "Informasi dari database sedang tidak tersedia."
        else:
            logger.warning("RAG system not available, using fallback")
            context = "Sistem pencarian informasi sedang dalam perbaikan."
        
        # Prepare enhanced prompt for Gemini
        full_prompt = f"""
Anda adalah asisten ahli bernama Ecombot yang memiliki pengetahuan tentang:

TOPIK UTAMA:
1. Kimia Hijau (Green Chemistry) dan 12 prinsipnya
2. Tradisi Mapag Hujan di Jawa Barat (Bandung dan Subang)
3. Filosofi Sunda seperti Seba Tangkal Muru Cai
4. Program Maraton Bebersih Walungan dan Susukan
5. Konservasi lingkungan dan mitigasi banjir
6. Pendidikan STEM (Science, Technology, Engineering, Arts, Mathematics)

INFORMASI KONTEKS:
{context}

PERTANYAAN USER:
{question}

INSTRUKSI:
1. Jawablah dengan bahasa Indonesia yang jelas dan mudah dipahami
2. Jika informasi dari konteks tidak cukup, gunakan pengetahuan umum Anda
3. Fokus pada topik-topik utama di atas
4. Berikan jawaban yang informatif dan membantu
5. Jika pertanyaan di luar topik, jelaskan dengan sopan dan arahkan ke topik yang relevan

JAWABAN:
"""
        
        # Get answer from Gemini
        answer = query_gemini(full_prompt)
        
        # Log the interaction for debugging
        logger.info(f"Q: {question} | A: {answer[:100]}... | Docs: {len(relevant_docs)}")
        
        return Response({
            "answer": answer.strip(),
            "sources_count": len(relevant_docs),
            "rag_system": "active" if retriever and relevant_docs else "fallback"
        })
        
    except Exception as e:
        logger.error(f"Unexpected error in ask_question: {e}")
        return Response(
            {"answer": "Maaf, terjadi kesalahan sistem. Silakan coba lagi dalam beberapa saat atau hubungi administrator."}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ===== ENDPOINT DEBUG & HEALTH CHECK =====

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint dengan debugging detail"""
    rag_status = "initialized" if retriever else "failed"
    api_key_info = {
        "available": bool(API_KEY),
        "length": len(API_KEY) if API_KEY else 0,
        "starts_with": API_KEY[:10] + "..." if API_KEY else "N/A"
    }
    
    # Check file existence
    csv_exists = os.path.exists(CSV_PATH)
    persist_exists = os.path.exists(PERSIST_DIR)
    
    return Response({
        "status": "healthy", 
        "rag_system": rag_status,
        "api_key": api_key_info,
        "model": MODEL,
        "files": {
            "csv_exists": csv_exists,
            "csv_path": CSV_PATH,
            "persist_dir_exists": persist_exists,
            "persist_dir": PERSIST_DIR
        }
    })

@api_view(['GET'])
@permission_classes([AllowAny])
def debug_rag_status(request):
    """Debug endpoint to check RAG system status"""
    try:
        status_info = {
            "rag_system": "initialized" if retriever else "not_initialized",
            "api_key_available": bool(API_KEY),
            "csv_file_exists": os.path.exists(CSV_PATH),
            "vectorstore_exists": os.path.exists(PERSIST_DIR) and os.listdir(PERSIST_DIR),
            "csv_path": CSV_PATH,
            "persist_dir": PERSIST_DIR,
            "model": MODEL
        }
        
        # Test retriever if available
        if retriever:
            try:
                test_docs = retriever.get_relevant_documents("kimia hijau")
                status_info["retriever_test"] = {
                    "success": True,
                    "documents_found": len(test_docs)
                }
            except Exception as e:
                status_info["retriever_test"] = {
                    "success": False,
                    "error": str(e)
                }
        
        return Response(status_info)
        
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ===== ENDPOINT RELOAD RAG SYSTEM =====

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reload_rag_system(request):
    """Endpoint to reload RAG system"""
    try:
        global retriever
        retriever = initialize_rag_system()
        
        if retriever:
            return Response({
                "status": "success", 
                "message": "RAG system reloaded successfully"
            })
        else:
            return Response({
                "status": "error", 
                "message": "Failed to reload RAG system"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        logger.error(f"Error reloading RAG system: {e}")
        return Response({
            "status": "error", 
            "message": f"Error reloading RAG system: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ===== ENDPOINT FORCE RELOAD (ALIAS) =====


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def force_rag_reload(request):
    """Force reload RAG system (admin only)"""
    try:
        global retriever
        retriever = initialize_rag_system()
        
        if retriever:
            return Response({
                "status": "success", 
                "message": "RAG system reloaded successfully"
            })
        else:
            return Response({
                "status": "error", 
                "message": "Failed to reload RAG system"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        logger.error(f"Error reloading RAG system: {e}")
        return Response({
            "status": "error", 
            "message": f"Error reloading RAG system: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ===== VIEWS KETIGA (CHATBOT ACTIVITY SYSTEM - PERBAIKAN) =====

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_chat_session(request):
    """Memulai sesi chat baru untuk kegiatan pembelajaran"""
    try:
        session_id = request.data.get('session_id', f"session_{timezone.now().strftime('%Y%m%d_%H%M%S')}")
        
        session, created = ChatSession.objects.get_or_create(
            user=request.user,
            session_id=session_id,
            defaults={
                'current_step': 'intro',
                'status': 'active'
            }
        )
        
        # Jika session baru, buat pesan intro
        if created:
            intro_data = CHATBOT_FLOW['intro']
            ChatMessage.objects.create(
                session=session,
                message_type='bot',
                character=intro_data.get('character', 'Aquano'),
                message_text=intro_data.get('message', ''),
                message_data={
                    'title': intro_data.get('title'),
                    'image_url': intro_data.get('image_url'),
                    'image_source': intro_data.get('image_source'),
                    'question': intro_data.get('question'),
                    'next_keywords': intro_data.get('next_keywords', [])
                },
                step_id=intro_data.get('id', 'intro')
            )
            
            # Buat user progress
            UserProgress.objects.create(
                user=request.user,
                session=session,
                current_kegiatan='intro',
                total_answers=0,
                completed_activities=['intro']
            )
        
        return Response({
            'status': 'success',
            'session_id': session.session_id,
            'current_activity': session.current_step,
            'message': 'Sesi chat berhasil dimulai'
        })
        
    except Exception as e:
        logger.error(f"Error starting chat session: {e}")
        return Response({
            'status': 'error',
            'message': 'Gagal memulai sesi chat'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_chat_message(request):
    """Mengirim pesan dan mendapatkan respons bot dalam kegiatan pembelajaran"""
    try:
        session_id = request.data.get('session_id')
        message_type = request.data.get('message_type')
        character = request.data.get('character')
        message_text = request.data.get('message_text')
        step_id = request.data.get('step_id')
        message_data = request.data.get('message_data', {})
        
        if not all([session_id, message_type, message_text, step_id]):
            return Response({
                'status': 'error',
                'message': 'Data tidak lengkap'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Dapatkan session
        try:
            session = ChatSession.objects.get(session_id=session_id, user=request.user)
        except ChatSession.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Sesi tidak ditemukan'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Simpan pesan
        message = ChatMessage.objects.create(
            session=session,
            message_type=message_type,
            character=character,
            message_text=message_text,
            message_data=message_data,
            step_id=step_id
        )
        
        # Update session current step
        session.current_step = step_id
        session.save()
        
        return Response({
            'status': 'success',
            'message_id': message.id,
            'timestamp': message.timestamp
        })
        
    except Exception as e:
        logger.error(f"Error sending chat message: {e}")
        return Response({
            'status': 'error',
            'message': 'Gagal mengirim pesan'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_activity_history(request, session_id, activity_id):
    """Mendapatkan histori percakapan untuk activity tertentu"""
    try:
        session = ChatSession.objects.get(session_id=session_id, user=request.user)
        
        messages = ChatMessage.objects.filter(
            session=session,
            step_id=activity_id
        ).order_by('timestamp')
        
        answers = UserAnswer.objects.filter(
            session=session,
            step_id=activity_id
        ).order_by('created_at')
        
        history = {
            'messages': ChatMessageSerializer(messages, many=True).data,
            'answers': UserAnswerSerializer(answers, many=True).data
        }
        
        return Response({
            'status': 'success',
            'session_id': session_id,
            'activity_id': activity_id,
            'history': history
        })
        
    except ChatSession.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Sesi tidak ditemukan'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error getting activity history: {e}")
        return Response({
            'status': 'error',
            'message': 'Gagal mengambil histori'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_session_overview(request, session_id):
    """Mendapatkan overview seluruh sesi"""
    try:
        session = ChatSession.objects.get(session_id=session_id, user=request.user)
        
        activities = [
            'intro', 'kimia_hijau', 'pre_kegiatan', 
            'kegiatan_1', 'kegiatan_2', 'kegiatan_3', 'kegiatan_4',
            'kegiatan_5', 'kegiatan_6', 'kegiatan_7', 'completion'
        ]
        
        overview = {}
        for activity in activities:
            messages_count = ChatMessage.objects.filter(
                session=session, step_id=activity
            ).count()
            
            answers_count = UserAnswer.objects.filter(
                session=session, step_id=activity
            ).count()
            
            try:
                activity_progress = ActivityProgress.objects.get(
                    session=session, activity_id=activity
                )
                status = activity_progress.status
            except ActivityProgress.DoesNotExist:
                status = 'not_started'
            
            overview[activity] = {
                'messages_count': messages_count,
                'answers_count': answers_count,
                'status': status
            }
        
        return Response({
            'status': 'success',
            'overview': overview
        })
        
    except ChatSession.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Sesi tidak ditemukan'
        }, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_activity_answer(request):
    """Menyimpan jawaban user untuk activity tertentu"""
    try:
        session_id = request.data.get('session_id')
        activity_id = request.data.get('activity_id')
        question_data = request.data.get('question_data')
        answer_text = request.data.get('answer_text', '')
        answer_type = request.data.get('answer_type', 'essay')
        
        if not all([session_id, activity_id, question_data]):
            return Response({
                'status': 'error',
                'message': 'Session ID, Activity ID, dan Question Data diperlukan'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Dapatkan session
        try:
            session = ChatSession.objects.get(session_id=session_id, user=request.user)
        except ChatSession.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Sesi tidak ditemukan'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Simpan jawaban
        answer = UserAnswer.objects.create(
            session=session,
            question_id=question_data.get('id'),
            storage_key=question_data.get('storage_key'),
            answer_text=answer_text,
            answer_type=answer_type,
            question_text=question_data.get('text', ''),
            step_id=activity_id,
            is_submitted=True,
            submitted_at=timezone.now()
        )
        
        # Update user progress
        user_progress, created = UserProgress.objects.get_or_create(
            user=request.user,
            session=session,
            defaults={
                'current_kegiatan': activity_id,
                'total_answers': 1,
                'completed_activities': [activity_id]
            }
        )
        
        if not created:
            user_progress.total_answers += 1
            if activity_id not in user_progress.completed_activities:
                user_progress.completed_activities.append(activity_id)
            user_progress.save()
        
        return Response({
            'status': 'success',
            'message': 'Jawaban berhasil disimpan',
            'answer_id': answer.id
        })
        
    except Exception as e:
        logger.error(f"Error submitting activity answer: {e}")
        return Response({
            'status': 'error',
            'message': 'Gagal menyimpan jawaban'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_activity(request):
    """Menandai activity sebagai selesai"""
    try:
        session_id = request.data.get('session_id')
        activity_id = request.data.get('activity_id')
        
        if not session_id or not activity_id:
            return Response({
                'status': 'error',
                'message': 'Session ID dan Activity ID diperlukan'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Dapatkan session
        try:
            session = ChatSession.objects.get(session_id=session_id, user=request.user)
        except ChatSession.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Sesi tidak ditemukan'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Tandai activity sebagai selesai
        activity_progress, created = ActivityProgress.objects.get_or_create(
            session=session,
            activity_id=activity_id,
            defaults={
                'status': 'completed',
                'answers_submitted': True,
                'completed_at': timezone.now()
            }
        )
        
        if not created:
            activity_progress.status = 'completed'
            activity_progress.answers_submitted = True
            activity_progress.completed_at = timezone.now()
            activity_progress.save()
        
        return Response({
            'status': 'success',
            'message': f'Activity {activity_id} berhasil diselesaikan'
        })
        
    except Exception as e:
        logger.error(f"Error completing activity: {e}")
        return Response({
            'status': 'error',
            'message': 'Gagal menandai activity sebagai selesai'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q

def _int_or_default(value, default):
    """Helper function to safely parse integer"""
    try:
        return int(value) if value else default
    except (ValueError, TypeError):
        return default


@api_view(["GET"])
def teacher_answers(request):
    try:
        # Hapus select_related yang salah
        qs = UserAnswer.objects.select_related("session__user").all()

        q = request.GET.get("q")
        activity = request.GET.get("activity")
        answer_type = request.GET.get("answer_type")
        date_from = request.GET.get("date_from")
        date_to = request.GET.get("date_to")
        ordering = request.GET.get("ordering", "-created_at")

        if q:
            qs = qs.filter(
                Q(session__user__username__icontains=q) |
                Q(answer_text__icontains=q) |
                Q(question_text__icontains=q)
            )
        if activity:
            qs = qs.filter(activity_id__icontains=activity)
        if answer_type:
            qs = qs.filter(answer_type=answer_type)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        # ordering validation
        if ordering in ['created_at', '-created_at']:
            qs = qs.order_by(ordering)
        else:
            qs = qs.order_by("-created_at")

        # pagination
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 25))
        paginator = Paginator(qs, page_size)
        
        try:
            page_obj = paginator.get_page(page)
        except Exception as e:
            return Response(
                {"error": f"Pagination error: {str(e)}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        data = []
        start_no = (page_obj.number - 1) * page_size + 1
        for idx, a in enumerate(page_obj.object_list, start=start_no):
            data.append({
                "no": idx,
                "nama_siswa": a.session.user.username if a.session and a.session.user else "-",
                "kegiatan": a.activity_id or "-",  # Gunakan activity_id karena bukan ForeignKey
                "jenis_pertanyaan": a.answer_type or "text",
                "pertanyaan": a.question_text or "",
                "jawaban_siswa": a.answer_text or "",
                "tipe_jawaban": a.answer_type or "",
                "tanggal_dikirim": a.created_at.strftime("%Y-%m-%d %H:%M") if a.created_at else "",
            })

        meta = {
            "page": page_obj.number,
            "page_size": page_size,
            "total_pages": paginator.num_pages,
            "total_items": paginator.count,
        }
        return Response({"meta": meta, "results": data}, status=status.HTTP_200_OK)
    
    except Exception as e:
        import traceback
        print("ERROR in teacher_answers:", str(e))
        print(traceback.format_exc())
        return Response(
            {"error": str(e), "detail": "Internal server error"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["GET"])
def teacher_dashboard(request):
    try:
        users = User.objects.all()

        username = request.GET.get("username")
        if username:
            users = users.filter(username__icontains=username)

        data_list = []
        for user in users:
            try:
                session = ChatSession.objects.filter(user=user).order_by("-updated_at").first()
                progress = UserProgress.objects.filter(user=user).first()
                last_activity_progress = ActivityProgress.objects.filter(session__user=user).order_by("-updated_at").first()
                total_answers = UserAnswer.objects.filter(session__user=user).count()

                data_list.append({
                    "siswa": user.username,
                    "komik": last_activity_progress.activity_id if last_activity_progress else "-",
                    "halaman_terakhir": progress.current_kegiatan if progress else "-",
                    "status_komik": "Selesai" if (last_activity_progress and last_activity_progress.status == "completed") else "Belum",
                    "chat_status": session.status if session else "-",
                    "kegiatan": last_activity_progress.activity_id if last_activity_progress else "-",
                    "jawaban_terkumpul": total_answers,
                })
            except Exception as e:
                print(f"Error processing user {user.username}: {str(e)}")
                continue

        # Filter after building data
        komik = request.GET.get("komik")
        status_komik = request.GET.get("status_komik")
        chat_status = request.GET.get("chat_status")
        
        if komik:
            data_list = [d for d in data_list if komik.lower() in d['komik'].lower()]
        if status_komik:
            data_list = [d for d in data_list if d['status_komik'].lower() == status_komik.lower()]
        if chat_status:
            data_list = [d for d in data_list if str(d['chat_status']).lower() == chat_status.lower()]

        # Pagination
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 25))
        paginator = Paginator(data_list, page_size)
        
        page_obj = paginator.get_page(page)

        meta = {
            "page": page_obj.number,
            "page_size": page_size,
            "total_pages": paginator.num_pages,
            "total_items": paginator.count,
        }
        return Response({"meta": meta, "results": list(page_obj)}, status=status.HTTP_200_OK)
    
    except Exception as e:
        import traceback
        print("ERROR in teacher_dashboard:", str(e))
        print(traceback.format_exc())
        return Response(
            {"error": str(e), "detail": "Internal server error"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    

# Load environment variables
load_dotenv()

@api_view(['POST'])
@permission_classes([AllowAny])
def verify_teacher_password(request):
    """
    POST /api/teacher/verify-password/
    Body: { "password": "your_password" }
    
    Verifikasi password guru dari .env file
    """
    try:
        input_password = request.data.get('password', '')
        
        # Ambil password dari .env
        correct_password = os.getenv('TEACHER_PASSWORD', 'greenverse2024')
        
        if not input_password:
            return Response(
                {
                    'success': False,
                    'message': 'Password tidak boleh kosong'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verifikasi password
        if input_password == correct_password:
            return Response(
                {
                    'success': True,
                    'message': 'Password benar'
                },
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {
                    'success': False,
                    'message': 'Password salah'
                },
                status=status.HTTP_401_UNAUTHORIZED
            )
            
    except Exception as e:
        print(f"Error in verify_teacher_password: {str(e)}")
        return Response(
            {
                'success': False,
                'message': 'Terjadi kesalahan server'
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )