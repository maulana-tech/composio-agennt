"""
Strategy Agent Logic - Analyzing and generating strategy diagrams.
"""
import os
import json
import re
from typing import AsyncGenerator
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

async def analyze_strategic_prompt_logic(prompt: str) -> str:
    """Analyze a strategic prompt to identify stakeholders and goals."""
    # This matches the implementation in strategy_diagram_agent.py
    llm = ChatGroq(model="llama-3.1-70b-versatile", temperature=0.2)
    prompt_template = ChatPromptTemplate.from_template("Analyze this: {prompt}")
    chain = prompt_template | llm
    return chain.invoke({"prompt": prompt}).content

async def generate_mermaid_logic(analysis_json: str, custom_style: str = "professional") -> str:
    """Generate Mermaid diagram code from analysis."""
    llm = ChatGroq(model="llama-3.1-70b-versatile", temperature=0.1)
    prompt = f"Generate Mermaid for: {analysis_json} with style {custom_style}"
    return llm.invoke(prompt).content
