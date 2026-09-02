"""Deterministic tools for the Prompt Optimizer Skill.

These tools perform only computation: format validation, deterministic
scoring of predictions against gold answers, metric calculation, and
guardrail checks. They never perform inference — the calling Agent (the LLM)
produces predictions and the LLM-judgement steps itself.
"""
