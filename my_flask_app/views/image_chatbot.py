from datetime import datetime
from flask import Blueprint, url_for, request, render_template, g, flash, jsonify
from werkzeug.utils import redirect
from langchain_openai import OpenAI
from langgraph.graph import StateGraph, START, END, MessagesState
from langchain_core.messages import AIMessage, HumanMessage  # HumanMessage 추가
from langgraph.checkpoint.memory import MemorySaver
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.prompts import PromptTemplate
import os
from dotenv import load_dotenv
from openai import OpenAI
import sqlite3

load_dotenv()  # .env에 작성한 변수를 불러온다.

bp = Blueprint('image', __name__, url_prefix='/imagebot')

@bp.route('/image', methods=['GET'])
def image_chat_page():
    return render_template('chatbot/image_chatbot.html')

@bp.route('/image', methods=['POST'])
def image():
    try:
        model_id = os.getenv('IMAGE_MODEL_ID')
        model = ImageChatModel(model_id=model_id)
        user_input = request.json.get('message')
        response = model.get_response(user_input)
        return jsonify({'response': response})
    
    except Exception as e:
        print(str(e))
        return jsonify({'error': str(e)}), 500

class ImageChatModel:
    def __init__(self, model_id):
        self.graph_builder = StateGraph(MessagesState)
        self.graph_builder.add_node('model', self._call_model)
        self.graph_builder.set_entry_point('model')
        self.memory = MemorySaver()
        self.graph = self.graph_builder.compile(checkpointer=self.memory)
        self.config = {'configurable': {'thread_id': '1'}}

        # 시스템 프롬프트 설정 - 이미지 광고 생성을 위한 역할 지정
        self.system_prompt = {
            "role": "system",
            "content": (
                "너는 텍스트와 이미지 광고를 만드는 AI야. 사용자 요청에 맞는 최신 트렌드 정보를 기반으로 광고용 이미지를 생성해줘. "
                "광고와 무관한 질문에는 '죄송합니다, 저는 광고 작성에만 도움을 드릴 수 있습니다.'라고 답하세요."
            )
        }

    def _call_model(self, state: MessagesState):
        # 최신 트렌드를 검색하여 검색 결과를 시스템 프롬프트에 추가
        # search_results = self.tool.invoke("최신 트렌드")  # 예시 키워드, 실제 사용 시에는 사용자 주제 관련 키워드 사용
        # print("Search Results:", search_results)  # 구조 확인

        # 검색 결과에서 title 추출, title이 없을 경우 "제목 없음" 반환
        # trends = [result.get("title", "제목 없음") for result in search_results]

        # 사용자 입력과 최신 트렌드를 결합하여 프롬프트 작성
        # if isinstance(state['messages'][0], HumanMessage):  # HumanMessage 객체 확인
        #     user_message = state['messages'][0].content
        # else:
        #     user_message = state['messages'][0].get('content', '')

        # prompt_content = f"{user_message} 최신 트렌드 참고: {', '.join(trends)}"
        
        # 시스템 프롬프트와 사용자 메시지를 결합
        # messages_with_prompt = [self.system_prompt, {"role": "user", "content": prompt_content}]
        
        
        prompt = PromptTemplate(
            input_variables=["image_desc"],
            template="Generate a detailed prompt to generate an image based on the following description: {image_desc}",
        )
        
        client = OpenAI()

        # 사용자 입력과 최신 트렌드를 결합하여 프롬프트 작성
        if isinstance(state['messages'][0], HumanMessage):  # HumanMessage 객체 확인
            user_message = state['messages'][0].content
        else:
            user_message = state['messages'][0].get('content', '')    

        response = client.images.generate(
            model="dall-e-3",
            prompt=user_message,
        )

        return {'messages': response.data[0].url}
    
    def get_response(self, prompt: str):
        try:
            response = self.graph.invoke({'messages': prompt}, config=self.config)
            print(response)
            for message in response['messages']:
                if isinstance(message, AIMessage):
                    if message.content == "":
                        continue
                    if isinstance(message.content, str):
                        return message.content
                    elif len(message.content) > 0 and message.content[0]['type'] == 'text':
                        return message.content[0]['text']
                elif self.is_image_result(message):
                    return message.content
        except Exception as e:
            print(f"Error invoking the model: {str(e)}")
            return f"Error: {str(e)}"

    def is_image_result(self, message):
        return isinstance(message, HumanMessage) and message.content.startswith('https://')