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

# ===== IMPORT UNTUK CHATBOT DENGAN LANGGRAPH =====
import sys
import os
import pandas as pd
import json
import google.generativeai as genai
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from dotenv import load_dotenv
import logging

# ===== LANGGRAPH & LANGCHAIN IMPORTS =====
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.messages import trim_messages
from typing import Sequence, Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

# Setup logging
logger = logging.getLogger(__name__)

# Load environment variables
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(BASE_DIR, '.env')
load_dotenv(env_path)

# Configuration untuk chatbot
CSV_PATH = os.path.join(BASE_DIR, "data/data.csv")
PERSIST_DIR = os.path.join(BASE_DIR, "chroma_db")

# Load API key
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
MODEL_NAME = "gemini-2.0-flash-lite"  
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
TOP_K = 4

# Global variables
retriever = None
gemini_model = None
chatbot_app = None

# ===== CHATBOT FLOW CONFIGURATION =====
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

# ===== INISIALISASI MODEL GEMINI =====

def initialize_gemini_model():
    """Initialize Gemini model dengan error handling yang lebih baik"""
    try:
        if not API_KEY:
            logger.error("❌ API key tidak ditemukan di environment variables")
            logger.info("Pastikan GEMINI_API_KEY atau GOOGLE_API_KEY sudah di-set di .env file")
            return None
            
        # Gunakan LangChain ChatGoogleGenerativeAI tanpa setting verbose global
        model = ChatGoogleGenerativeAI(
            model=MODEL_NAME,
            google_api_key=API_KEY,
            temperature=0.7,
            max_tokens=1000,
            timeout=30
        )
        
        # Test the model dengan prompt sederhana
        try:
            test_response = model.invoke("Hello, test connection")
            if test_response and hasattr(test_response, 'content'):
                logger.info("✅ Gemini model initialized dan tested successfully")
                return model
            else:
                logger.error("❌ Gemini model test failed - no response content")
                return None
        except Exception as test_error:
            logger.error(f"❌ Gemini model test failed: {test_error}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error initializing Gemini model: {e}")
        return None    
        
# ===== LANGGRAPH CHATBOT SYSTEM =====

class ChatState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    session_id: str
    user_id: str
    current_activity: str

def create_chatbot_graph():
    """Membuat LangGraph chatbot dengan memory persistence"""
    try:
        # Define the graph
        workflow = StateGraph(state_schema=ChatState)
        
        # Define prompt template dengan konteks pembelajaran
        prompt_template = ChatPromptTemplate.from_messages([
            (
                "system",
                """Anda adalah Aquano, asisten virtual pembelajaran untuk Ecombot. Anda memiliki pengetahuan tentang:
                
                TOPIK UTAMA:
                1. Kimia Hijau (Green Chemistry) dan 12 prinsipnya
                2. Tradisi Mapag Hujan di Jawa Barat (Bandung dan Subang)
                3. Filosofi Sunda seperti Seba Tangkal Muru Cai
                4. Program Maraton Bebersih Walungan dan Susukan
                5. Konservasi lingkungan dan mitigasi banjir
                6. Pendidikan STEM (Science, Technology, Engineering, Arts, Mathematics)
                
                INSTRUKSI:
                - Jawablah dengan bahasa Indonesia yang jelas dan mudah dipahami
                - Bersikaplah ramah dan membantu seperti guru yang baik
                - Jika informasi tidak cukup, gunakan pengetahuan umum Anda
                - Fokus pada topik-topik utama di atas
                - Bimbing siswa melalui proses pembelajaran yang interaktif
                - Gunakan emoji sesekali untuk membuat percakapan lebih hidup
                """
            ),
            MessagesPlaceholder(variable_name="messages"),
        ])
        
        # Define the function that calls the model dengan RAG integration
        def call_model_with_rag(state: ChatState):
            """Memanggil model dengan konteks dari RAG system"""
            try:
                # Dapatkan pertanyaan terakhir dari user
                last_user_message = None
                for msg in reversed(state["messages"]):
                    if isinstance(msg, HumanMessage):
                        last_user_message = msg.content
                        break
                
                # Jika ada RAG system, dapatkan konteks relevan
                context = ""
                if retriever and last_user_message:
                    try:
                        docs = retriever.get_relevant_documents(last_user_message)
                        context = "\n\n".join([d.page_content for d in docs[:2]])  # Ambil 2 dokumen teratas
                        logger.info(f"RAG retrieved {len(docs)} documents for question")
                    except Exception as e:
                        logger.error(f"Error retrieving RAG documents: {e}")
                        context = "Informasi dari database sedang tidak tersedia."
                
                # Siapkan prompt dengan konteks
                if context:
                    enhanced_prompt = f"""
KONTEKS TAMBAHAN:
{context}

PERTANYAAN USER:
{last_user_message}

JAWABAN (gunakan bahasa Indonesia yang jelas dan membantu):
"""
                    # Buat messages baru dengan konteks
                    enhanced_messages = []
                    for msg in state["messages"]:
                        if isinstance(msg, HumanMessage) and msg.content == last_user_message:
                            # Ganti pesan user dengan yang sudah diperkaya konteks
                            enhanced_messages.append(HumanMessage(content=enhanced_prompt))
                        else:
                            enhanced_messages.append(msg)
                    
                    prompt = prompt_template.invoke({"messages": enhanced_messages})
                else:
                    prompt = prompt_template.invoke(state)
                
                # Panggil model
                response = gemini_model.invoke(prompt)
                
                # Simpan interaksi ke database untuk analytics
                try:
                    session = ChatSession.objects.get(session_id=state["session_id"])
                    ChatMessage.objects.create(
                        session=session,
                        message_type='bot',
                        character='Aquano',
                        message_text=response.content,
                        step_id=state.get("current_activity", "general"),
                        activity_id=state.get("current_activity", "general")
                    )
                except Exception as db_error:
                    logger.error(f"Error saving chat message to DB: {db_error}")
                
                return {"messages": [response]}
                
            except Exception as e:
                logger.error(f"Error in call_model_with_rag: {e}")
                # Fallback response
                fallback_response = AIMessage(
                    content="Maaf, saya mengalami gangguan teknis. Silakan coba lagi atau hubungi administrator."
                )
                return {"messages": [fallback_response]}
        
        # Add nodes and edges
        workflow.add_node("model", call_model_with_rag)
        workflow.add_edge(START, "model")
        
        # Add memory persistence
        memory = MemorySaver()
        app = workflow.compile(checkpointer=memory)
        
        logger.info("✅ LangGraph chatbot system initialized successfully")
        return app
        
    except Exception as e:
        logger.error(f"Error creating LangGraph chatbot: {e}")
        return None

# ===== RAG SYSTEM =====

def create_fallback_retriever():
    """Create a fallback retriever tanpa sentence-transformers"""
    try:
        logger.info("Creating simple fallback retriever...")
        
        # Gunakan documents sederhana tanpa embeddings complex
        fallback_docs = [
            Document(
                page_content="""
                Kimia Hijau (Green Chemistry) adalah pendekatan dalam ilmu kimia yang bertujuan merancang produk dan proses kimia yang mengurangi atau menghilangkan penggunaan dan pembentukan zat berbahaya. Ada 12 prinsip kimia hijau yang meliputi pencegahan limbah, atom economy, desain bahan kimia yang lebih aman, dan penggunaan energi yang efisien.
                """,
                metadata={"topic": "Kimia Hijau", "category": "education"}
            ),
            Document(
                page_content="""
                Tradisi Mapag Hujan adalah tradisi masyarakat Jawa Barat khususnya di Bandung dan Subang yang bertujuan menyambut musim hujan dengan membersihkan lingkungan, sungai, dan saluran air. Tradisi ini merupakan bentuk kearifan lokal dalam mitigasi banjir dan pelestarian lingkungan.
                """,
                metadata={"topic": "Mapag Hujan", "category": "culture"}
            )
        ]
        
        # Untuk fallback, kita buat simple retriever tanpa embeddings
        class SimpleFallbackRetriever:
            def __init__(self, docs):
                self.docs = docs
            
            def get_relevant_documents(self, query):
                # Return semua dokumen untuk semua query (sangat sederhana)
                return self.docs
            
            async def aget_relevant_documents(self, query):
                return self.docs
        
        retriever = SimpleFallbackRetriever(fallback_docs)
        logger.info("[+] Simple fallback retriever created successfully")
        return retriever
        
    except Exception as e:
        logger.error(f"Error creating simple fallback retriever: {e}")
        return None
    
def create_simple_csv_retriever():
    """Create a simple retriever that searches directly in CSV"""
    try:
        logger.info("Creating simple CSV retriever...")
        
        # Load CSV data directly
        df = pd.read_csv(CSV_PATH, dtype=str).fillna("")
        logger.info(f"Loaded CSV with {len(df)} rows")
        
        # Prepare documents
        documents = []
        for _, row in df.iterrows():
            # Create rich content for better retrieval
            content = f"""
Topic: {row.get('topic', '')}
Question: {row.get('question', '')}  
Answer: {row.get('answer', '')}
Keywords: {row.get('keywords', '')}
Context: {row.get('context', '')}
Category: {row.get('category', '')}
""".strip()
            
            if content:
                metadata = {
                    'id': row.get('id', ''),
                    'topic': row.get('topic', ''),
                    'category': row.get('category', ''),
                    'source': 'ecombot_knowledge_base'
                }
                documents.append(Document(page_content=content, metadata=metadata))

        logger.info(f"Processed {len(documents)} documents")

        class SimpleCSVRetriever:
            def __init__(self, docs):
                self.docs = docs
            
            def get_relevant_documents(self, query):
                query_lower = query.lower().strip()
                scored_docs = []
                
                for doc in self.docs:
                    score = 0
                    content_lower = doc.page_content.lower()
                    
                    # Exact match scoring
                    if query_lower in content_lower:
                        score += 20
                    
                    # Individual word matching dengan bobot lebih tinggi
                    query_words = query_lower.split()
                    for word in query_words:
                        if len(word) > 2:  # Kata dengan minimal 3 karakter
                            if word in content_lower:
                                score += 5
                    
                    # Boost score untuk dokumen yang sangat relevan
                    if any(keyword in content_lower for keyword in ['ecombot', 'greenverse', 'pembuat', 'pencipta', 'tim']):
                        score += 10
                    
                    if score > 0:
                        scored_docs.append((score, doc))
                
                # Sort by score descending
                scored_docs.sort(key=lambda x: x[0], reverse=True)
                
                # Return top documents
                return [doc for score, doc in scored_docs[:5]]
            
            async def aget_relevant_documents(self, query):
                return self.get_relevant_documents(query)
        
        retriever = SimpleCSVRetriever(documents)
        logger.info("✅ Simple CSV retriever created successfully")
        
        # Test dengan query spesifik
        test_query = "Siapa yang membuat ECOMBOT?"
        test_docs = retriever.get_relevant_documents(test_query)
        logger.info(f"🧪 Test retrieval for '{test_query}': Found {len(test_docs)} docs")
        
        for i, doc in enumerate(test_docs):
            logger.info(f"   Test Doc {i+1}: {doc.page_content[:100]}...")
        
        return retriever
        
    except Exception as e:
        logger.error(f"Error creating simple CSV retriever: {e}")
        return None
    
def initialize_rag_system():
    """Initialize the RAG system - menggunakan simple retriever untuk reliability"""
    global retriever
    try:
        logger.info("=== STARTING RAG INITIALIZATION (SIMPLE MODE) ===")
        
        # Gunakan simple CSV retriever untuk reliability
        retriever = create_simple_csv_retriever()
        
        if retriever:
            logger.info("✅ RAG system initialized successfully dengan simple retriever")
            return retriever
        else:
            logger.error("❌ Failed to initialize simple retriever")
            return create_fallback_retriever()
        
    except Exception as e:
        logger.error(f"❌ Error initializing RAG system: {e}")
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
        
    


def initialize_all_systems():
    """Initialize semua sistem sekaligus dengan error handling yang lebih baik"""
    global gemini_model, chatbot_app, retriever
    
    logger.info("🔄 Initializing all systems...")
    
    status_report = {}
    
    # Initialize Gemini Model
    try:
        gemini_model = initialize_gemini_model()
        status_report["gemini_model"] = "✅ Ready" if gemini_model else "❌ Failed"
        logger.info(f"Gemini Model: {status_report['gemini_model']}")
    except Exception as e:
        logger.error(f"Gemini initialization failed: {e}")
        status_report["gemini_model"] = f"❌ Failed: {str(e)}"
        gemini_model = None
    
    # Initialize RAG System
    try:
        retriever = initialize_rag_system()
        status_report["rag_system"] = "✅ Ready" if retriever else "❌ Failed"
        logger.info(f"RAG System: {status_report['rag_system']}")
    except Exception as e:
        logger.error(f"RAG initialization failed: {e}")
        status_report["rag_system"] = f"❌ Failed: {str(e)}"
        retriever = None
    
    # Initialize LangGraph Chatbot
    try:
        if gemini_model:
            chatbot_app = create_chatbot_graph()
            status_report["langgraph_chatbot"] = "✅ Ready" if chatbot_app else "❌ Failed"
        else:
            status_report["langgraph_chatbot"] = "❌ Failed: No Gemini model"
            chatbot_app = None
        logger.info(f"LangGraph Chatbot: {status_report['langgraph_chatbot']}")
    except Exception as e:
        logger.error(f"LangGraph initialization failed: {e}")
        status_report["langgraph_chatbot"] = f"❌ Failed: {str(e)}"
        chatbot_app = None
    
    logger.info(f"System Status: {status_report}")
    return status_report

# Panggil initialization dengan error handling
try:
    initialize_all_systems()
except Exception as e:
    logger.error(f"Failed to initialize systems: {e}")
    
    
# Initialize semua sistem
initialize_all_systems()

# ===== VIEWS UTAMA =====

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

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ecombot(request):
    return Response({
        "message": f"Halo, {request.user.username}! Ini halaman profil kamu."
    })

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

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def comic_mark_finish(request):
    """
    POST /api/comic-progress/finish/
    body: { "comic": "...", "episode": "...", "last_page": 3, "complete": true }
    """
    user = request.user
    comic = request.data.get("comic")
    episode = request.data.get("episode")
    last_page_body = request.data.get("last_page")
    complete_flag = bool(request.data.get("complete", False))
    force = bool(request.data.get("force", False))

    REQUIRED_PAGE_THRESHOLD = 3

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
@permission_classes([AllowAny])
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

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response({"detail": "Refresh token tidak diberikan"}, status=status.HTTP_400_BAD_REQUEST)

            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"detail": "Logout berhasil"}, status=status.HTTP_205_RESET_CONTENT)
        except TokenError:
            return Response({"detail": "Token tidak valid atau sudah kadaluarsa"}, status=status.HTTP_400_BAD_REQUEST)

# ===== CHATBOT VIEWS DENGAN LANGGRAPH =====

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_chat_session(request):
    """Memulai sesi chat baru dengan LangGraph"""
    try:
        session_id = request.data.get('session_id', f"session_{timezone.now().strftime('%Y%m%d_%H%M%S')}")
        activity_id = request.data.get('activity_id', 'intro')
        
        # Buat atau dapatkan session
        session, created = ChatSession.objects.get_or_create(
            user=request.user,
            session_id=session_id,
            defaults={
                'current_step': activity_id,
                'status': 'active'
            }
        )
        
        # Jika session baru, inisialisasi di LangGraph
        if created and chatbot_app:
            config = {"configurable": {"thread_id": session_id}}
            
            # Buat pesan pembuka
            opening_message = "Halo! 👋 Saya Aquano, asisten pembelajaran Ecombot. Saya siap membantu Anda menjelajahi dunia Kimia Hijau dan Tradisi Mapag Hujan. Ada yang bisa saya bantu hari ini?"
            
            # Simpan ke database
            ChatMessage.objects.create(
                session=session,
                message_type='bot',
                character='Aquano',
                message_text=opening_message,
                step_id=activity_id,
                activity_id=activity_id
            )
            
            # Buat user progress
            UserProgress.objects.create(
                user=request.user,
                session=session,
                current_kegiatan=activity_id,
                total_answers=0,
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

def send_chat_message_fallback(session, message_text, activity_id):
    """Fallback method jika LangGraph tidak tersedia"""
    try:
        # Gunakan RAG system langsung
        if retriever:
            try:
                docs = retriever.get_relevant_documents(message_text)
                context = "\n\n".join([d.page_content for d in docs[:2]])
                
                prompt = f"""
KONTEKS:
{context}

PERTANYAAN USER:
{message_text}

JAWABAN (gunakan bahasa Indonesia yang jelas dan membantu):
"""
            except Exception as rag_error:
                logger.error(f"RAG error: {rag_error}")
                prompt = message_text
        else:
            prompt = message_text
        
        # Gunakan Gemini langsung
        if gemini_model:
            response = gemini_model.invoke(prompt)
            bot_response = response.content
        else:
            bot_response = "Maaf, sistem sedang dalam perbaikan. Silakan coba lagi nanti."
        
        # Simpan ke database
        bot_message = ChatMessage.objects.create(
            session=session,
            message_type='bot',
            character='Aquano',
            message_text=bot_response,
            step_id=activity_id,
            activity_id=activity_id
        )
        
        session.current_step = activity_id
        session.save()
        
        return Response({
            'status': 'success',
            'message_id': bot_message.id,
            'timestamp': bot_message.timestamp,
            'response': bot_response,
            'session_id': session.session_id
        })
        
    except Exception as e:
        logger.error(f"Error in fallback chat: {e}")
        return Response({
            'status': 'error',
            'message': 'Gagal memproses pesan'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_chat_message(request):
    """Mengirim pesan dan mendapatkan respons menggunakan LangGraph"""
    try:
        session_id = request.data.get('session_id')
        message_text = request.data.get('message_text')
        activity_id = request.data.get('activity_id', 'general')
        
        if not all([session_id, message_text]):
            return Response({
                'status': 'error',
                'message': 'session_id dan message_text diperlukan'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Dapatkan session
        try:
            session = ChatSession.objects.get(session_id=session_id, user=request.user)
        except ChatSession.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Sesi tidak ditemukan'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Simpan pesan user ke database
        user_message = ChatMessage.objects.create(
            session=session,
            message_type='user',
            character='User',
            message_text=message_text,
            step_id=activity_id,
            activity_id=activity_id
        )
        
        # Process dengan LangGraph jika tersedia
        if chatbot_app:
            try:
                config = {"configurable": {"thread_id": session_id}}
                
                # Prepare state untuk LangGraph
                input_state = {
                    "messages": [HumanMessage(content=message_text)],
                    "session_id": session_id,
                    "user_id": str(request.user.id),
                    "current_activity": activity_id
                }
                
                # Invoke LangGraph
                output = chatbot_app.invoke(input_state, config)
                
                # Dapatkan respons terakhir
                bot_response = None
                for msg in reversed(output["messages"]):
                    if isinstance(msg, AIMessage):
                        bot_response = msg.content
                        break
                
                if bot_response:
                    # Simpan respons bot ke database
                    bot_message = ChatMessage.objects.create(
                        session=session,
                        message_type='bot',
                        character='Aquano',
                        message_text=bot_response,
                        step_id=activity_id,
                        activity_id=activity_id
                    )
                    
                    # Update session
                    session.current_step = activity_id
                    session.save()
                    
                    return Response({
                        'status': 'success',
                        'message_id': bot_message.id,
                        'timestamp': bot_message.timestamp,
                        'response': bot_response,
                        'session_id': session_id
                    })
                    
            except Exception as graph_error:
                logger.error(f"LangGraph error: {graph_error}")
                # Fallback ke sistem lama jika LangGraph gagal
                return send_chat_message_fallback(session, message_text, activity_id)
        else:
            # Fallback jika LangGraph tidak tersedia
            return send_chat_message_fallback(session, message_text, activity_id)
            
    except Exception as e:
        logger.error(f"Error in send_chat_message: {e}")
        return Response({
            'status': 'error',
            'message': 'Gagal mengirim pesan'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def ask_question(request):
    """Handle question asking dengan RAG system atau fallback"""
    try:
        question = request.data.get('question', '').strip()
        
        if not question:
            return Response(
                {"answer": "Silakan ajukan pertanyaan yang lebih spesifik."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        logger.info(f"🔍 Processing question: '{question}'")
        
        # Get relevant documents from RAG system atau fallback
        context = ""
        relevant_docs = []
        rag_status = "fallback"
        
        if retriever:
            try:
                docs = retriever.get_relevant_documents(question)
                logger.info(f"📄 Retrieved {len(docs)} documents for question: '{question}'")
                
                # LOG DETAIL SETIAP DOKUMEN YANG DITEMUKAN
                for i, doc in enumerate(docs):
                    logger.info(f"   📝 Doc {i+1} Content: {doc.page_content}")
                    logger.info(f"   🏷️  Doc {i+1} Metadata: {doc.metadata}")
                    logger.info("   " + "-" * 50)
                
                context = "\n\n".join([f"Dokumen {i+1}:\n{d.page_content}" for i, d in enumerate(docs)])
                relevant_docs = docs
                rag_status = "active" if docs else "no_docs"
                
            except Exception as e:
                logger.error(f"❌ Error retrieving documents: {e}")
                context = "Sistem pencarian informasi sedang dalam perbaikan."
                rag_status = "error"
        else:
            logger.warning("RAG system not available, using direct Gemini")
            context = "Sistem pencarian informasi sedang dalam perbaikan."
            rag_status = "not_available"
        
        # Prepare prompt dengan konteks yang lebih jelas
        if context and rag_status == "active":
            full_prompt = f"""
INFORMASI KONTEKS YANG DITEMUKAN:
{context}

PERTANYAAN USER:
{question}

INSTRUKSI: 
- Jawab pertanyaan berdasarkan informasi dalam konteks di atas
- Jika informasi tersedia dalam konteks, berikan jawaban yang akurat
- Jika informasi tidak tersedia dalam konteks, jelaskan bahwa informasi tidak ditemukan
- Gunakan bahasa Indonesia yang jelas dan informatif

JAWABAN:
"""
        else:
            full_prompt = f"""
PERTANYAAN USER:
{question}

JAWABAN (gunakan bahasa Indonesia yang jelas dan informatif. Jika tidak tahu jawabannya, jelaskan bahwa informasi tidak tersedia):
"""
        
        # Get answer from Gemini
        answer = "Maaf, sistem AI sedang tidak tersedia. Silakan coba lagi nanti."
        if gemini_model:
            try:
                logger.info(f"🤖 Sending prompt to Gemini...")
                response = gemini_model.invoke(full_prompt)
                answer = response.content.strip()
                logger.info(f"✅ Gemini response: {answer[:200]}...")
            except Exception as gemini_error:
                logger.error(f"❌ Gemini error: {gemini_error}")
                answer = "Maaf, terjadi kesalahan saat memproses pertanyaan Anda."
        
        # Log the interaction
        logger.info(f"📊 Summary - Q: '{question}' | A: {answer[:100]}... | RAG: {rag_status} | Docs: {len(relevant_docs)}")
        
        return Response({
            "answer": answer,
            "sources_count": len(relevant_docs),
            "rag_system": rag_status
        })
        
    except Exception as e:
        logger.error(f"❌ Unexpected error in ask_question: {e}")
        return Response(
            {"answer": "Maaf, terjadi kesalahan sistem. Silakan coba lagi dalam beberapa saat."}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
        
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_activity_answer(request):
    """Menyimpan jawaban user untuk activity tertentu"""
    try:
        session_id = request.data.get('session_id')
        activity_id = request.data.get('activity_id')
        question_data = request.data.get('question_data', {})
        answer_text = request.data.get('answer_text', '')
        answer_type = request.data.get('answer_type', 'essay')
        
        if not all([session_id, activity_id]):
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
        
        # Extract question data
        if isinstance(question_data, str):
            try:
                question_data = json.loads(question_data)
            except:
                question_data = {}
        
        question_id = question_data.get('id') or f"question_{int(timezone.now().timestamp())}"
        storage_key = question_data.get('storage_key') or f"storage_{question_id}"
        question_text = question_data.get('text') or question_data.get('question_text') or 'Pertanyaan tidak tersedia'
        
        # Cek atau buat jawaban
        existing_answer = UserAnswer.objects.filter(
            session=session,
            question_id=question_id
        ).first()
        
        if existing_answer:
            existing_answer.answer_text = answer_text
            existing_answer.answer_type = answer_type
            existing_answer.question_text = question_text
            existing_answer.step_id = activity_id
            existing_answer.activity_id = activity_id
            existing_answer.is_submitted = True
            existing_answer.submitted_at = timezone.now()
            existing_answer.save()
            answer = existing_answer
            action = 'updated'
        else:
            answer = UserAnswer.objects.create(
                session=session,
                question_id=question_id,
                storage_key=storage_key,
                answer_text=answer_text,
                answer_type=answer_type,
                question_text=question_text,
                step_id=activity_id,
                activity_id=activity_id,
                is_submitted=True,
                submitted_at=timezone.now()
            )
            action = 'created'
        
        # Update progress
        user_progress, created = UserProgress.objects.get_or_create(
            user=request.user,
            session=session,
            defaults={
                'current_kegiatan': activity_id,
                'total_answers': 1,
            }
        )
        
        if not created:
            total_submitted = UserAnswer.objects.filter(
                session=session, 
                is_submitted=True
            ).count()
            user_progress.total_answers = total_submitted
            user_progress.current_kegiatan = activity_id
            user_progress.save()
        
        # Update activity progress
        activity_progress, created = ActivityProgress.objects.get_or_create(
            session=session,
            activity_id=activity_id,
            defaults={
                'status': 'completed',
                'completed_at': timezone.now()
            }
        )
        
        if not created:
            activity_progress.status = 'completed'
            activity_progress.completed_at = timezone.now()
            activity_progress.save()
        
        # Response data
        answer_data = {
            'id': answer.id,
            'question_id': answer.question_id,
            'answer_text': answer.answer_text,
            'answer_type': answer.answer_type,
            'question_text': answer.question_text,
            'activity_id': answer.activity_id,
            'is_submitted': answer.is_submitted,
            'submitted_at': answer.submitted_at.isoformat() if answer.submitted_at else None,
        }
        
        completed_activities_count = ActivityProgress.objects.filter(
            session=session,
            status='completed'
        ).count()
        
        return Response({
            'status': 'success',
            'message': 'Jawaban berhasil disimpan',
            'action': action,
            'answer': answer_data,
            'progress': {
                'total_answers': user_progress.total_answers,
                'current_activity': user_progress.current_kegiatan,
                'completed_activities_count': completed_activities_count
            }
        })
        
    except Exception as e:
        logger.error(f"Error submitting activity answer: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Gagal menyimpan jawaban: {str(e)}'
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
                'completed_at': timezone.now()
            }
        )
        
        if not created:
            activity_progress.status = 'completed'
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

# ===== TEACHER VIEWS =====

@api_view(['POST'])
@permission_classes([AllowAny])
def verify_teacher_password(request):
    """Verifikasi password guru dari .env file"""
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

from django.core.paginator import Paginator
from django.db.models import Q, Count

@api_view(["GET"])
@permission_classes([AllowAny])
def teacher_answers(request):
    """GET /api/teacher/answers/"""
    try:
        # Query dengan filter untuk memastikan data valid
        qs = UserAnswer.objects.select_related(
            "session__user"
        ).exclude(
            session__isnull=True
        ).exclude(
            session__user__isnull=True
        )

        # Filter berdasarkan query params
        q = request.GET.get("q", "").strip()
        activity = request.GET.get("activity", "").strip()
        answer_type = request.GET.get("answer_type", "").strip()
        date_from = request.GET.get("date_from", "").strip()
        date_to = request.GET.get("date_to", "").strip()
        ordering = request.GET.get("ordering", "-created_at")

        # Search filter
        if q:
            qs = qs.filter(
                Q(session__user__username__icontains=q) |
                Q(answer_text__icontains=q) |
                Q(question_text__icontains=q)
            )
        
        # Activity filter
        if activity:
            qs = qs.filter(activity_id__icontains=activity)
        
        # Answer type filter
        if answer_type:
            qs = qs.filter(answer_type=answer_type)
        
        # Date range filter
        if date_from:
            try:
                qs = qs.filter(created_at__date__gte=date_from)
            except Exception as e:
                print(f"Invalid date_from format: {e}")
        
        if date_to:
            try:
                qs = qs.filter(created_at__date__lte=date_to)
            except Exception as e:
                print(f"Invalid date_to format: {e}")

        # Ordering validation
        allowed_orderings = ['created_at', '-created_at', 'updated_at', '-updated_at']
        if ordering not in allowed_orderings:
            ordering = '-created_at'
        qs = qs.order_by(ordering)

        # Pagination
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 25))
        page_size = min(page_size, 100)
        
        paginator = Paginator(qs, page_size)
        
        try:
            page_obj = paginator.get_page(page)
        except Exception as e:
            return Response(
                {"error": f"Pagination error: {str(e)}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Build response data
        data = []
        start_no = (page_obj.number - 1) * page_size + 1
        
        for idx, answer in enumerate(page_obj.object_list, start=start_no):
            # Safe data extraction
            try:
                username = answer.session.user.username if (answer.session and answer.session.user) else "Unknown"
            except:
                username = "Unknown"
            
            activity_name = answer.activity_id or answer.step_id or "-"
            
            # Format tanggal dengan fallback
            try:
                tanggal = answer.created_at.strftime("%Y-%m-%d %H:%M") if answer.created_at else "-"
            except:
                tanggal = "-"
            
            data.append({
                "no": idx,
                "id": answer.id,
                "nama_siswa": username,
                "kegiatan": activity_name,
                "jenis_pertanyaan": answer.answer_type or "essay",
                "pertanyaan": answer.question_text or "-",
                "jawaban_siswa": answer.answer_text or "-",
                "image_url": answer.image_url or None,
                "tipe_jawaban": answer.answer_type or "essay",
                "status": "Submitted" if answer.is_submitted else "Draft",
                "tanggal_dikirim": tanggal,
            })

        # Metadata
        meta = {
            "page": page_obj.number,
            "page_size": page_size,
            "total_pages": paginator.num_pages,
            "total_items": paginator.count,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
        }
        
        return Response({
            "meta": meta, 
            "results": data
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print("ERROR in teacher_answers:")
        print(str(e))
        print(error_trace)
        
        return Response(
            {
                "error": str(e), 
                "detail": "Internal server error",
            }, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(["GET"])
@permission_classes([AllowAny])
def teacher_dashboard(request):
    """GET /api/teacher/dashboard/"""
    try:
        # Get all users
        users = User.objects.all().order_by('username')

        # Filter by username
        username_filter = request.GET.get("username", "").strip()
        if username_filter:
            users = users.filter(username__icontains=username_filter)

        data_list = []
        
        for user in users:
            try:
                # Dapatkan data comic progress
                comic_progress = UserComicProgress.objects.filter(
                    user=user
                ).order_by('-updated_at').first()
                
                # Dapatkan chat session
                chat_session = ChatSession.objects.filter(
                    user=user
                ).order_by('-updated_at').first()
                
                # Dapatkan user progress
                user_progress = UserProgress.objects.filter(
                    user=user
                ).order_by('-updated_at').first()
                
                # Dapatkan activity progress terakhir
                last_activity = ActivityProgress.objects.filter(
                    session__user=user
                ).order_by('-last_accessed').first()
                
                # Hitung total jawaban
                total_answers = UserAnswer.objects.filter(
                    session__user=user,
                    is_submitted=True
                ).count()
                
                # Data Komik
                if comic_progress:
                    comic_name = f"{comic_progress.comic_slug} - {comic_progress.episode_slug}"
                    last_page = comic_progress.last_page
                    comic_status = "Selesai" if comic_progress.finish else "Belum Selesai"
                else:
                    comic_name = "-"
                    last_page = 0
                    comic_status = "Belum Mulai"
                
                # Data Chat/Kegiatan
                if chat_session:
                    chat_status_value = chat_session.status
                    current_step = chat_session.current_step
                else:
                    chat_status_value = "not_started"
                    current_step = "-"
                
                # Kegiatan terakhir
                if last_activity:
                    last_kegiatan = last_activity.activity_id
                    kegiatan_status = last_activity.status
                elif user_progress:
                    last_kegiatan = user_progress.current_kegiatan
                    kegiatan_status = "in_progress"
                else:
                    last_kegiatan = "-"
                    kegiatan_status = "not_started"
                
                data_list.append({
                    "siswa": user.username,
                    "user_id": user.id,
                    
                    # Data Komik
                    "komik": comic_name,
                    "halaman_terakhir": last_page,
                    "status_komik": comic_status,
                    
                    # Data Kegiatan Pembelajaran
                    "chat_status": chat_status_value,
                    "current_step": current_step,
                    "kegiatan_terakhir": last_kegiatan,
                    "status_kegiatan": kegiatan_status,
                    
                    # Statistik
                    "jawaban_terkumpul": total_answers,
                    
                    # Timestamp
                    "terakhir_aktif": (
                        chat_session.updated_at.strftime("%Y-%m-%d %H:%M")
                        if chat_session and chat_session.updated_at
                        else "-"
                    )
                })
                
            except Exception as e:
                print(f"Error processing user {user.username}: {str(e)}")
                continue

        # Filter setelah data terbentuk
        komik_filter = request.GET.get("komik", "").strip()
        status_komik_filter = request.GET.get("status_komik", "").strip()
        chat_status_filter = request.GET.get("chat_status", "").strip()
        
        if komik_filter:
            data_list = [
                d for d in data_list 
                if komik_filter.lower() in d['komik'].lower()
            ]
        
        if status_komik_filter:
            data_list = [
                d for d in data_list 
                if d['status_komik'].lower() == status_komik_filter.lower()
            ]
        
        if chat_status_filter:
            data_list = [
                d for d in data_list 
                if str(d['chat_status']).lower() == chat_status_filter.lower()
            ]

        # Pagination
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 25))
        page_size = min(page_size, 100)
        
        paginator = Paginator(data_list, page_size)
        page_obj = paginator.get_page(page)

        # Metadata
        meta = {
            "page": page_obj.number,
            "page_size": page_size,
            "total_pages": paginator.num_pages,
            "total_items": paginator.count,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
        }
        
        return Response({
            "meta": meta, 
            "results": list(page_obj)
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print("ERROR in teacher_dashboard:")
        print(str(e))
        
        return Response(
            {
                "error": str(e), 
                "detail": "Internal server error",
            }, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(["GET"])
@permission_classes([AllowAny])
def teacher_student_detail(request, username):
    """GET /api/teacher/student/<username>/"""
    try:
        user = User.objects.get(username=username)
        
        # Comic Progress
        comic_progress_list = UserComicProgress.objects.filter(
            user=user
        ).order_by('-updated_at')
        
        comics_data = [{
            "comic_slug": cp.comic_slug,
            "episode_slug": cp.episode_slug,
            "last_page": cp.last_page,
            "finish": cp.finish,
            "updated_at": cp.updated_at.strftime("%Y-%m-%d %H:%M")
        } for cp in comic_progress_list]
        
        # Chat Sessions
        chat_sessions = ChatSession.objects.filter(
            user=user
        ).order_by('-updated_at')
        
        sessions_data = [{
            "session_id": cs.session_id,
            "current_step": cs.current_step,
            "status": cs.status,
            "created_at": cs.created_at.strftime("%Y-%m-%d %H:%M"),
            "updated_at": cs.updated_at.strftime("%Y-%m-%d %H:%M")
        } for cs in chat_sessions]
        
        # Activity Progress
        activity_progress_list = ActivityProgress.objects.filter(
            session__user=user
        ).order_by('activity_id')
        
        activities_data = [{
            "activity_id": ap.activity_id,
            "status": ap.status,
            "last_accessed": ap.last_accessed.strftime("%Y-%m-%d %H:%M"),
            "completed_at": ap.completed_at.strftime("%Y-%m-%d %H:%M") if ap.completed_at else None
        } for ap in activity_progress_list]
        
        # Answers
        total_answers = UserAnswer.objects.filter(
            session__user=user,
            is_submitted=True
        ).count()
        
        # Statistics
        answers_by_activity = UserAnswer.objects.filter(
            session__user=user,
            is_submitted=True
        ).values('activity_id').annotate(
            count=Count('id')
        ).order_by('activity_id')
        
        return Response({
            "username": username,
            "user_id": user.id,
            "comics": comics_data,
            "chat_sessions": sessions_data,
            "activities": activities_data,
            "statistics": {
                "total_answers": total_answers,
                "answers_by_activity": list(answers_by_activity)
            }
        }, status=status.HTTP_200_OK)
        
    except User.DoesNotExist:
        return Response(
            {"error": "User tidak ditemukan"}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        import traceback
        print(f"Error in teacher_student_detail: {str(e)}")
        print(traceback.format_exc())
        return Response(
            {"error": str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ===== DEBUG & HEALTH ENDPOINTS =====

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint dengan debugging detail"""
    try:
        # Test each system
        gemini_test = False
        if gemini_model:
            try:
                test_response = gemini_model.invoke("Test")
                gemini_test = bool(test_response and hasattr(test_response, 'content'))
            except:
                gemini_test = False
        
        rag_test = False
        if retriever:
            try:
                test_docs = retriever.get_relevant_documents("test")
                rag_test = len(test_docs) > 0
            except:
                rag_test = False
        
        langgraph_test = bool(chatbot_app)
        
        systems_status = {
            "rag_system": "✅ Ready" if rag_test else "❌ Failed",
            "langgraph_chatbot": "✅ Ready" if langgraph_test else "❌ Failed",
            "gemini_model": "✅ Ready" if gemini_test else "❌ Failed"
        }
        
        api_key_info = {
            "available": bool(API_KEY),
            "length": len(API_KEY) if API_KEY else 0,
            "starts_with": API_KEY[:10] + "..." if API_KEY else "N/A"
        }
        
        # Check file existence
        csv_exists = os.path.exists(CSV_PATH)
        persist_exists = os.path.exists(PERSIST_DIR) and os.listdir(PERSIST_DIR)
        
        health_data = {
            "status": "healthy" if all([gemini_test, rag_test, langgraph_test]) else "degraded",
            "systems": systems_status,
            "api_key": api_key_info,
            "model": MODEL_NAME,
            "files": {
                "csv_exists": csv_exists,
                "csv_path": CSV_PATH,
                "persist_dir_exists": persist_exists,
                "persist_dir": PERSIST_DIR
            },
            "timestamp": timezone.now().isoformat()
        }
        
        return Response(health_data)
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return Response({
            "status": "error",
            "message": f"Health check failed: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
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
            "model": MODEL_NAME
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

@api_view(['POST'])
@permission_classes([AllowAny])
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

@api_view(['POST'])
@permission_classes([AllowAny])
def force_rag_reload(request):
    """Alias for reload_rag_system for backward compatibility"""
    return reload_rag_system(request)

@api_view(['POST'])
@permission_classes([AllowAny])
def reload_all_systems(request):
    """Reload semua sistem sekaligus"""
    try:
        status_report = initialize_all_systems()
        
        success_count = sum(1 for status in status_report.values() if "Ready" in status)
        total_systems = len(status_report)
        
        return Response({
            "status": "success",
            "message": f"Reloaded {success_count}/{total_systems} systems",
            "systems_status": status_report
        })
        
    except Exception as e:
        logger.error(f"Error reloading all systems: {e}")
        return Response({
            "status": "error",
            "message": f"Error reloading systems: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ===== ACTIVITY HISTORY ENDPOINTS =====

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