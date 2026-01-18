#!/usr/bin/env python3
"""Kanban dashboard with smooth drag-and-drop."""

from flask import Flask, render_template_string, request, jsonify
from datetime import datetime, UTC

from core.models import Quote, Post, PostStatus, init_db, get_session

app = Flask(__name__)

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EdgeOfICT Social</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-deep: #08090a;
            --bg-card: #0d1117;
            --bg-elevated: #161b22;
            --border: #21262d;
            --border-bright: #30363d;
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --text-muted: #6e7681;
            --accent-cyan: #00d4ff;
            --accent-purple: #a78bfa;
            --accent-blue: #58a6ff;
            --accent-green: #4ade80;
            --accent-yellow: #fbbf24;
            --accent-red: #f87171;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-deep);
            min-height: 100vh;
            color: var(--text-primary);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(90deg, rgba(0,212,255,0.06), rgba(167,139,250,0.06));
            border-bottom: 1px solid var(--border);
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            backdrop-filter: blur(12px);
        }

        .logo {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.25rem;
            font-weight: 600;
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-purple));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.5px;
        }

        .stats-bar { display: flex; gap: 2rem; font-size: 0.8rem; }
        .stat { display: flex; align-items: center; gap: 0.5rem; }
        .stat-num {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            color: var(--accent-cyan);
        }
        .stat-label { color: var(--text-muted); text-transform: uppercase; font-size: 0.7rem; letter-spacing: 0.5px; }

        .kanban {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1rem;
            padding: 1.25rem;
            height: calc(100vh - 65px);
        }

        .column {
            background: var(--bg-elevated);
            border: 1px solid var(--border);
            border-radius: 12px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            transition: border-color 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                        box-shadow 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                        transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .column.drag-over {
            border-color: var(--accent-blue);
            box-shadow: 0 0 0 1px var(--accent-blue),
                        inset 0 0 30px rgba(88, 166, 255, 0.08),
                        0 8px 32px rgba(88, 166, 255, 0.12);
            transform: scale(1.01);
        }

        .column-header {
            padding: 1rem 1rem 0.75rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .column-title {
            font-weight: 600;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-secondary);
        }
        .column-count {
            font-family: 'JetBrains Mono', monospace;
            background: var(--border);
            color: var(--text-muted);
            padding: 0.2rem 0.6rem;
            border-radius: 6px;
            font-size: 0.7rem;
            font-weight: 500;
        }

        .column-body {
            flex: 1;
            overflow-y: auto;
            padding: 0.5rem;
            min-height: 200px;
        }

        .card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 0.875rem;
            margin-bottom: 0.5rem;
            cursor: grab;
            position: relative;
            user-select: none;
            -webkit-user-select: none;
            touch-action: none;
            will-change: transform, opacity, box-shadow;
            transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1),
                        box-shadow 0.2s cubic-bezier(0.4, 0, 0.2, 1),
                        border-color 0.2s ease;
        }

        .card:hover {
            border-color: var(--accent-blue);
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(88, 166, 255, 0.2);
        }

        .card:active { cursor: grabbing; }

        .card.is-dragging {
            opacity: 0.35;
            transform: scale(0.98);
            border-style: dashed;
            border-color: var(--accent-blue);
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .drag-ghost {
            position: fixed;
            pointer-events: none;
            z-index: 10000;
            will-change: transform, opacity;
            border-radius: 10px;
            background: var(--bg-card);
            border: 2px solid var(--accent-cyan);
            box-shadow: 0 25px 60px rgba(0, 0, 0, 0.5),
                        0 0 0 1px rgba(0, 212, 255, 0.3),
                        0 0 40px rgba(0, 212, 255, 0.15);
            opacity: 0;
            transition: opacity 0.2s ease, box-shadow 0.2s ease;
        }

        .drag-ghost.visible {
            opacity: 1;
        }

        .drag-ghost.dropping {
            opacity: 0;
            transition: opacity 0.2s ease, transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
        }

        .card-content {
            font-size: 0.8rem;
            line-height: 1.55;
            margin-bottom: 0.625rem;
            color: var(--text-primary);
        }

        .card-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 0.375rem;
            align-items: center;
        }

        .tag {
            padding: 0.2rem 0.5rem;
            border-radius: 6px;
            font-size: 0.65rem;
            font-weight: 500;
            font-family: 'JetBrains Mono', monospace;
        }

        .tag-topic { background: rgba(167, 139, 250, 0.15); color: var(--accent-purple); }
        .tag-source {
            padding: 0.2rem 0.6rem;
            max-width: 140px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .tag-score { background: rgba(88, 166, 255, 0.15); color: var(--accent-blue); }

        .card.approved { border-left: 3px solid var(--accent-green); }
        .card.pending { border-left: 3px solid var(--accent-yellow); }
        .card.posted { border-left: 3px solid var(--accent-blue); opacity: 0.7; }

        .post-meta { justify-content: space-between; font-size: 0.7rem; color: var(--text-secondary); }

        .status-dot {
            width: 6px; height: 6px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 0.35rem;
        }
        .status-dot.approved { background: var(--accent-green); box-shadow: 0 0 8px var(--accent-green); }
        .status-dot.pending { background: var(--accent-yellow); box-shadow: 0 0 8px var(--accent-yellow); }
        .status-dot.posted { background: var(--accent-blue); box-shadow: 0 0 8px var(--accent-blue); }
        .status-dot.quote { background: var(--accent-purple); box-shadow: 0 0 8px var(--accent-purple); }

        .char-count { font-size: 0.65rem; font-family: 'JetBrains Mono', monospace; }
        .char-ok { color: var(--accent-green); }
        .char-warn { color: var(--accent-yellow); }
        .char-over { color: var(--accent-red); }

        .col-quotes .column-header { border-bottom: 2px solid var(--text-muted); }
        .col-approved .column-header { border-bottom: 2px solid var(--accent-green); }
        .col-pending .column-header { border-bottom: 2px solid var(--accent-yellow); }
        .col-posted .column-header { border-bottom: 2px solid var(--accent-blue); }

        .btn-shuffle {
            background: transparent;
            border: 1px solid var(--border);
            border-radius: 6px;
            color: var(--text-secondary);
            padding: 0.3rem 0.6rem;
            font-size: 0.7rem;
            font-family: 'Outfit', sans-serif;
            font-weight: 500;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 0.35rem;
            transition: all 0.2s ease;
        }

        .btn-shuffle:hover {
            border-color: var(--accent-cyan);
            color: var(--accent-cyan);
            background: rgba(0, 212, 255, 0.08);
        }

        .btn-shuffle svg {
            width: 12px;
            height: 12px;
        }

        .btn-shuffle.shuffling svg {
            animation: shuffleSpin 0.5s ease;
        }

        @keyframes shuffleSpin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .column-header-left {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .empty-state {
            text-align: center;
            padding: 2rem 1rem;
            color: var(--text-muted);
            font-size: 0.8rem;
            border: 2px dashed var(--border);
            border-radius: 10px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .empty-state.drag-over {
            border-color: var(--accent-blue);
            background: rgba(88, 166, 255, 0.08);
            color: var(--accent-blue);
        }

        .drop-placeholder {
            height: 4px;
            border-radius: 2px;
            background: linear-gradient(90deg, var(--accent-cyan), var(--accent-purple));
            margin: 0.25rem 0;
            opacity: 0;
            transform: scaleX(0.3);
            transition: all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
            box-shadow: 0 0 12px var(--accent-cyan);
        }

        .drop-placeholder.visible {
            opacity: 1;
            transform: scaleX(1);
        }

        .toast {
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            background: linear-gradient(135deg, #238636, #2ea043);
            color: white;
            padding: 0.875rem 1.5rem;
            border-radius: 10px;
            font-size: 0.875rem;
            font-weight: 500;
            opacity: 0;
            transform: translateY(20px) scale(0.95);
            transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
            z-index: 10001;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
        }
        .toast.show { opacity: 1; transform: translateY(0) scale(1); }
        .toast.error { background: linear-gradient(135deg, #da3633, #f85149); }

        .column-body::-webkit-scrollbar { width: 4px; }
        .column-body::-webkit-scrollbar-track { background: transparent; }
        .column-body::-webkit-scrollbar-thumb { background: var(--border-bright); border-radius: 2px; }

        /* Modal */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.85);
            backdrop-filter: blur(8px);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 9999;
            opacity: 0;
            transition: opacity 0.2s ease;
        }

        .modal-overlay.show {
            display: flex;
            opacity: 1;
        }

        .modal {
            background: var(--bg-deep);
            border: 1px solid var(--border-bright);
            border-radius: 16px;
            width: 100%;
            max-width: 560px;
            max-height: 90vh;
            overflow-y: auto;
            transform: scale(0.95) translateY(10px);
            transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
        }

        .modal-overlay.show .modal {
            transform: scale(1) translateY(0);
        }

        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem 1.25rem;
            border-bottom: 1px solid var(--border);
        }

        .modal-close {
            background: none;
            border: none;
            color: var(--text-secondary);
            font-size: 1.5rem;
            cursor: pointer;
            padding: 0.5rem;
            border-radius: 50%;
            transition: all 0.2s;
            line-height: 1;
        }

        .modal-close:hover {
            background: rgba(255,255,255,0.08);
            color: var(--text-primary);
        }

        .x-post { padding: 1.25rem; }

        .x-header {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 1rem;
        }

        .x-avatar {
            width: 44px;
            height: 44px;
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-purple));
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 1.1rem;
            color: white;
            font-family: 'JetBrains Mono', monospace;
        }

        .x-user-info { flex: 1; }
        .x-name { font-weight: 600; color: var(--text-primary); font-size: 0.95rem; }
        .x-handle { color: var(--text-muted); font-size: 0.85rem; }

        .x-content {
            color: var(--text-primary);
            font-size: 1.05rem;
            line-height: 1.5;
            white-space: pre-wrap;
            margin-bottom: 1rem;
        }

        .x-hashtag { color: #1d9bf0; }

        .x-meta {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.75rem 0;
            border-top: 1px solid var(--border);
            color: var(--text-muted);
            font-size: 0.85rem;
        }

        .x-char-count { font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; }

        .x-actions {
            display: flex;
            justify-content: space-around;
            padding: 0.5rem 0;
            border-top: 1px solid var(--border);
        }

        .x-action {
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.85rem;
            cursor: pointer;
            padding: 0.5rem 0.75rem;
            border-radius: 8px;
            transition: all 0.2s;
        }

        .x-action:hover {
            background: rgba(29, 155, 240, 0.1);
            color: #1d9bf0;
        }

        .modal-status {
            padding: 0.75rem 1.25rem;
            border-top: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--bg-elevated);
        }

        .status-label {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.8rem;
            font-weight: 500;
        }

        .status-label.pending { color: var(--accent-yellow); }
        .status-label.approved { color: var(--accent-green); }
        .status-label.posted { color: var(--accent-blue); }
        .status-label.quote { color: var(--accent-purple); }

        body.is-dragging { cursor: grabbing !important; }
        body.is-dragging * { cursor: grabbing !important; }

        /* Create Button */
        .btn-create {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1rem;
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-purple));
            border: none;
            border-radius: 8px;
            color: white;
            font-family: 'Outfit', sans-serif;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 2px 8px rgba(0, 212, 255, 0.25);
        }

        .btn-create:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 16px rgba(0, 212, 255, 0.35);
        }

        .btn-create:active {
            transform: translateY(0);
        }

        .btn-create svg {
            width: 16px;
            height: 16px;
        }

        /* Upload Modal */
        .upload-modal {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.9);
            backdrop-filter: blur(12px);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 10000;
            opacity: 0;
            transition: opacity 0.25s ease;
        }

        .upload-modal.show {
            display: flex;
            opacity: 1;
        }

        .upload-panel {
            background: var(--bg-elevated);
            border: 1px solid var(--border-bright);
            border-radius: 16px;
            width: 100%;
            max-width: 500px;
            padding: 2rem;
            transform: scale(0.95) translateY(10px);
            transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
        }

        .upload-modal.show .upload-panel {
            transform: scale(1) translateY(0);
        }

        .upload-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
        }

        .upload-title {
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--text-primary);
        }

        .upload-close {
            background: none;
            border: none;
            color: var(--text-secondary);
            font-size: 1.5rem;
            cursor: pointer;
            padding: 0.25rem;
            line-height: 1;
            border-radius: 6px;
            transition: all 0.2s;
        }

        .upload-close:hover {
            background: rgba(255,255,255,0.08);
            color: var(--text-primary);
        }

        .upload-zone {
            border: 2px dashed var(--border-bright);
            border-radius: 12px;
            padding: 3rem 2rem;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            background: var(--bg-card);
        }

        .upload-zone:hover,
        .upload-zone.drag-over {
            border-color: var(--accent-cyan);
            background: rgba(0, 212, 255, 0.05);
        }

        .upload-zone.drag-over {
            transform: scale(1.02);
            box-shadow: 0 0 30px rgba(0, 212, 255, 0.15);
        }

        .upload-icon {
            width: 48px;
            height: 48px;
            margin: 0 auto 1rem;
            color: var(--accent-cyan);
            opacity: 0.8;
        }

        .upload-text {
            color: var(--text-secondary);
            font-size: 0.95rem;
            margin-bottom: 0.5rem;
        }

        .upload-hint {
            color: var(--text-muted);
            font-size: 0.8rem;
        }

        .upload-input {
            display: none;
        }

        .upload-file-info {
            display: none;
            align-items: center;
            gap: 1rem;
            padding: 1rem;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 10px;
            margin-top: 1rem;
        }

        .upload-file-info.show {
            display: flex;
        }

        .file-icon {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, var(--accent-purple), var(--accent-cyan));
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 600;
            font-size: 0.7rem;
            font-family: 'JetBrains Mono', monospace;
        }

        .file-details {
            flex: 1;
        }

        .file-name {
            font-weight: 500;
            color: var(--text-primary);
            font-size: 0.9rem;
            margin-bottom: 0.2rem;
        }

        .file-size {
            color: var(--text-muted);
            font-size: 0.75rem;
            font-family: 'JetBrains Mono', monospace;
        }

        .file-remove {
            background: none;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            padding: 0.5rem;
            border-radius: 6px;
            transition: all 0.2s;
        }

        .file-remove:hover {
            background: rgba(248, 113, 113, 0.15);
            color: var(--accent-red);
        }

        .upload-actions {
            display: flex;
            gap: 0.75rem;
            margin-top: 1.5rem;
        }

        .btn-upload {
            flex: 1;
            padding: 0.875rem 1.5rem;
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-purple));
            border: none;
            border-radius: 10px;
            color: white;
            font-family: 'Outfit', sans-serif;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
        }

        .btn-upload:hover:not(:disabled) {
            transform: translateY(-1px);
            box-shadow: 0 4px 20px rgba(0, 212, 255, 0.3);
        }

        .btn-upload:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .btn-cancel {
            padding: 0.875rem 1.5rem;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 10px;
            color: var(--text-secondary);
            font-family: 'Outfit', sans-serif;
            font-size: 0.95rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }

        .btn-cancel:hover {
            border-color: var(--border-bright);
            color: var(--text-primary);
        }

        /* Processing State */
        .upload-processing {
            display: none;
            text-align: center;
            padding: 2rem;
        }

        .upload-processing.show {
            display: block;
        }

        .processing-spinner {
            width: 48px;
            height: 48px;
            margin: 0 auto 1.5rem;
            border: 3px solid var(--border);
            border-top-color: var(--accent-cyan);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .processing-text {
            color: var(--text-primary);
            font-size: 1rem;
            margin-bottom: 0.5rem;
        }

        .processing-subtext {
            color: var(--text-muted);
            font-size: 0.85rem;
        }

        /* Result State */
        .upload-result {
            display: none;
            text-align: center;
            padding: 2rem;
        }

        .upload-result.show {
            display: block;
        }

        .result-icon {
            width: 56px;
            height: 56px;
            margin: 0 auto 1rem;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .result-icon.success {
            background: rgba(74, 222, 128, 0.15);
            color: var(--accent-green);
        }

        .result-icon.error {
            background: rgba(248, 113, 113, 0.15);
            color: var(--accent-red);
        }

        .result-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 0.5rem;
        }

        .result-stats {
            display: flex;
            justify-content: center;
            gap: 2rem;
            margin: 1.5rem 0;
        }

        .result-stat {
            text-align: center;
        }

        .result-stat-num {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.75rem;
            font-weight: 600;
            color: var(--accent-cyan);
        }

        .result-stat-label {
            font-size: 0.8rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .btn-done {
            padding: 0.875rem 2rem;
            background: linear-gradient(135deg, var(--accent-green), #22c55e);
            border: none;
            border-radius: 10px;
            color: white;
            font-family: 'Outfit', sans-serif;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }

        .btn-done:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 20px rgba(74, 222, 128, 0.3);
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">EdgeOfICT Social</div>
        <div class="stats-bar">
            <div class="stat"><span class="stat-num" id="stat-quotes">{{ stats.total_quotes }}</span><span class="stat-label">quotes</span></div>
            <button class="btn-create" onclick="openUploadModal()">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
                    <path d="M12 5v14M5 12h14"/>
                </svg>
                Create
            </button>
            <div class="stat"><span class="stat-num">{{ stats.documents }}</span><span class="stat-label">docs</span></div>
            <div class="stat"><span class="stat-num" id="stat-unused">{{ stats.unused_quotes }}</span><span class="stat-label">unused</span></div>
            <div class="stat"><span class="stat-num" id="stat-posted">{{ stats.posted }}</span><span class="stat-label">posted</span></div>
        </div>
    </div>

    <div class="kanban">
        <div class="column col-quotes" data-status="quotes">
            <div class="column-header">
                <div class="column-header-left">
                    <span class="column-title">Fresh Quotes</span>
                    <button class="btn-shuffle" onclick="shuffleCards()" title="Shuffle cards">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="16 3 21 3 21 8"/>
                            <line x1="4" y1="20" x2="21" y2="3"/>
                            <polyline points="21 16 21 21 16 21"/>
                            <line x1="15" y1="15" x2="21" y2="21"/>
                            <line x1="4" y1="4" x2="9" y2="9"/>
                        </svg>
                        Shuffle
                    </button>
                </div>
                <span class="column-count">{{ fresh_quotes|length }}</span>
            </div>
            <div class="column-body">
                {% for quote in fresh_quotes %}
                <div class="card" data-type="quote" data-id="{{ quote.id }}" data-source="{{ quote.source }}">
                    <div class="card-content">"{{ quote.content }}"</div>
                    <div class="card-meta">
                        <span class="tag tag-topic">{{ quote.topic }}</span>
                        <span class="tag tag-source" data-source="{{ quote.source }}">{{ quote.source }}</span>
                        <span class="tag tag-score">{{ "%.1f"|format(quote.quality_score) }}</span>
                    </div>
                </div>
                {% else %}
                <div class="empty-state">No fresh quotes</div>
                {% endfor %}
            </div>
        </div>

        <div class="column col-pending" data-status="pending">
            <div class="column-header">
                <span class="column-title">Pending Review</span>
                <span class="column-count">{{ pending_posts|length }}</span>
            </div>
            <div class="column-body">
                {% for post in pending_posts %}
                <div class="card pending" data-type="post" data-id="{{ post.id }}">
                    <div class="card-content">{{ post.content[:140] }}{% if post.content|length > 140 %}...{% endif %}</div>
                    <div class="card-meta post-meta">
                        <span><span class="status-dot pending"></span>{{ post.scheduled_time.strftime('%b %d') if post.scheduled_time else 'Draft' }}</span>
                        <span class="char-count {{ 'char-ok' if post.content|length <= 250 else 'char-warn' if post.content|length <= 280 else 'char-over' }}">{{ post.content|length }}/280</span>
                    </div>
                </div>
                {% else %}
                <div class="empty-state">Drag quotes here</div>
                {% endfor %}
            </div>
        </div>

        <div class="column col-approved" data-status="approved">
            <div class="column-header">
                <span class="column-title">Approved</span>
                <span class="column-count">{{ approved_posts|length }}</span>
            </div>
            <div class="column-body">
                {% for post in approved_posts %}
                <div class="card approved" data-type="post" data-id="{{ post.id }}">
                    <div class="card-content">{{ post.content[:140] }}{% if post.content|length > 140 %}...{% endif %}</div>
                    <div class="card-meta post-meta">
                        <span><span class="status-dot approved"></span>{{ post.scheduled_time.strftime('%b %d') if post.scheduled_time else 'Ready' }}</span>
                        <span class="char-count {{ 'char-ok' if post.content|length <= 250 else 'char-warn' if post.content|length <= 280 else 'char-over' }}">{{ post.content|length }}/280</span>
                    </div>
                </div>
                {% else %}
                <div class="empty-state">Drag to approve</div>
                {% endfor %}
            </div>
        </div>

        <div class="column col-posted" data-status="posted">
            <div class="column-header">
                <span class="column-title">Posted</span>
                <span class="column-count">{{ posted_posts|length }}</span>
            </div>
            <div class="column-body">
                {% for post in posted_posts %}
                <div class="card posted" data-type="post" data-id="{{ post.id }}">
                    <div class="card-content">{{ post.content[:100] }}{% if post.content|length > 100 %}...{% endif %}</div>
                    <div class="card-meta post-meta">
                        <span><span class="status-dot posted"></span>{{ post.posted_time.strftime('%b %d') if post.posted_time else 'Done' }}</span>
                    </div>
                </div>
                {% else %}
                <div class="empty-state">Nothing posted yet</div>
                {% endfor %}
            </div>
        </div>
    </div>

    <div class="modal-overlay" id="modal">
        <div class="modal">
            <div class="modal-header">
                <span style="color: #e7e9ea; font-weight: 600;">Post Preview</span>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="x-post">
                <div class="x-header">
                    <div class="x-avatar">E</div>
                    <div class="x-user-info">
                        <div class="x-name">EdgeOfICT</div>
                        <div class="x-handle">@edgeofict</div>
                    </div>
                </div>
                <div class="x-content" id="modal-content"></div>
                <div class="x-meta">
                    <span id="modal-time"></span>
                    <span class="x-char-count" id="modal-chars"></span>
                </div>
                <div class="x-actions">
                    <span class="x-action">💬 Reply</span>
                    <span class="x-action">🔁 Repost</span>
                    <span class="x-action">❤️ Like</span>
                    <span class="x-action">📊 Views</span>
                </div>
            </div>
            <div class="modal-status">
                <span class="status-label" id="modal-status"></span>
                <span id="modal-source" style="color: #71767b; font-size: 0.85rem;"></span>
            </div>
        </div>
    </div>

    <div class="toast" id="toast"></div>

    <!-- Upload Modal -->
    <div class="upload-modal" id="uploadModal">
        <div class="upload-panel">
            <div class="upload-header">
                <span class="upload-title">Create Quotes from Document</span>
                <button class="upload-close" onclick="closeUploadModal()">&times;</button>
            </div>

            <div id="uploadForm">
                <div class="upload-zone" id="uploadZone">
                    <svg class="upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                        <polyline points="17 8 12 3 7 8"/>
                        <line x1="12" y1="3" x2="12" y2="15"/>
                    </svg>
                    <div class="upload-text">Drop your document here or click to browse</div>
                    <div class="upload-hint">Supports PDF and DOCX files</div>
                    <input type="file" class="upload-input" id="fileInput" accept=".pdf,.docx">
                </div>

                <div class="upload-file-info" id="fileInfo">
                    <div class="file-icon" id="fileExt">PDF</div>
                    <div class="file-details">
                        <div class="file-name" id="fileName">document.pdf</div>
                        <div class="file-size" id="fileSize">2.4 MB</div>
                    </div>
                    <button class="file-remove" onclick="removeFile()">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M18 6L6 18M6 6l12 12"/>
                        </svg>
                    </button>
                </div>

                <div class="upload-actions">
                    <button class="btn-cancel" onclick="closeUploadModal()">Cancel</button>
                    <button class="btn-upload" id="btnExtract" onclick="extractQuotes()" disabled>
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                        </svg>
                        Extract Quotes
                    </button>
                </div>
            </div>

            <div class="upload-processing" id="uploadProcessing">
                <div class="processing-spinner"></div>
                <div class="processing-text">Extracting quotes...</div>
                <div class="processing-subtext">This may take a minute depending on document size</div>
            </div>

            <div class="upload-result" id="uploadResult">
                <div class="result-icon success" id="resultIcon">
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                        <polyline points="20 6 9 17 4 12"/>
                    </svg>
                </div>
                <div class="result-title" id="resultTitle">Quotes Extracted!</div>
                <div class="result-stats">
                    <div class="result-stat">
                        <div class="result-stat-num" id="resultExtracted">0</div>
                        <div class="result-stat-label">Extracted</div>
                    </div>
                    <div class="result-stat">
                        <div class="result-stat-num" id="resultSaved">0</div>
                        <div class="result-stat-label">New Saved</div>
                    </div>
                </div>
                <button class="btn-done" onclick="finishUpload()">Done</button>
            </div>
        </div>
    </div>

    <script>
    // Store full content for posts (avoids HTML escaping issues in attributes)
    const POST_CONTENT = {
        {% for post in pending_posts %}'{{ post.id }}': {{ post.content | tojson }},
        {% endfor %}
        {% for post in approved_posts %}'{{ post.id }}': {{ post.content | tojson }},
        {% endfor %}
        {% for post in posted_posts %}'{{ post.id }}': {{ post.content | tojson }},
        {% endfor %}
    };

    (function() {
        'use strict';

        // Smooth drag-drop with frame-rate independent lerp
        const DRAG_THRESHOLD = 5;
        const SMOOTHING = 0.12;

        let drag = null;
        let ghost = null;
        let placeholder = null;
        let ghostPos = { x: 0, y: 0 };
        let targetPos = { x: 0, y: 0 };
        let animationId = null;
        let lastFrameTime = 0;

        // Modal functions
        function closeModal() {
            document.getElementById('modal').classList.remove('show');
        }

        function openModal(card) {
            const type = card.dataset.type;
            const cardId = card.dataset.id;
            const status = card.classList.contains('posted') ? 'posted' :
                           card.classList.contains('approved') ? 'approved' :
                           card.classList.contains('pending') ? 'pending' : 'quote';

            // Use POST_CONTENT for posts (properly JSON encoded), card content for quotes
            let displayContent;
            if (type === 'post' && POST_CONTENT[cardId]) {
                displayContent = POST_CONTENT[cardId];
            } else if (type === 'quote') {
                const quoteText = card.querySelector('.card-content').textContent;
                displayContent = quoteText + '\\n\\nTrack your edge.\\n\\n#EdgeOfICT #ICTTrading';
            } else {
                displayContent = card.querySelector('.card-content').textContent;
            }

            const formatted = displayContent.replace(/#(\\w+)/g, '<span class="x-hashtag">#$1</span>');
            document.getElementById('modal-content').innerHTML = formatted;
            document.getElementById('modal-chars').textContent = displayContent.length + '/280';
            document.getElementById('modal-chars').className = 'x-char-count ' +
                (displayContent.length <= 250 ? 'char-ok' : displayContent.length <= 280 ? 'char-warn' : 'char-over');

            const statusEl = document.getElementById('modal-status');
            statusEl.className = 'status-label ' + status;
            const icons = { quote: '📝 Quote', pending: '⏳ Pending', approved: '✓ Approved', posted: '✓ Posted' };
            statusEl.innerHTML = '<span class="status-dot ' + status + '"></span>' + icons[status];

            const sourceTag = card.querySelector('.tag-source');
            document.getElementById('modal-source').textContent = sourceTag ? sourceTag.textContent : '';

            const now = new Date();
            document.getElementById('modal-time').textContent = now.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }) + ' · ' + now.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

            document.getElementById('modal').classList.add('show');
        }

        document.getElementById('modal').addEventListener('click', function(e) {
            if (e.target === this) closeModal();
        });

        function showToast(msg, isError) {
            const t = document.getElementById('toast');
            t.textContent = msg;
            t.className = 'toast show' + (isError ? ' error' : '');
            setTimeout(() => t.className = 'toast', 2500);
        }

        // Animation loop for buttery smooth 60fps ghost movement
        function animateGhost(timestamp) {
            if (!ghost) return;

            // Frame-rate independent smoothing
            const deltaTime = lastFrameTime ? (timestamp - lastFrameTime) / 16.667 : 1;
            lastFrameTime = timestamp;

            // Exponential smoothing for natural deceleration
            const factor = 1 - Math.pow(1 - SMOOTHING, deltaTime);
            ghostPos.x += (targetPos.x - ghostPos.x) * factor;
            ghostPos.y += (targetPos.y - ghostPos.y) * factor;

            // Calculate velocity for dynamic rotation
            const velX = targetPos.x - ghostPos.x;
            const rotation = Math.max(-3, Math.min(3, velX * 0.02));

            // Apply transform with subtle dynamic rotation
            ghost.style.transform = `translate3d(${Math.round(ghostPos.x * 10) / 10}px, ${Math.round(ghostPos.y * 10) / 10}px, 0) scale(1.02) rotate(${rotation.toFixed(1)}deg)`;

            animationId = requestAnimationFrame(animateGhost);
        }

        function createGhost(card) {
            const rect = card.getBoundingClientRect();
            const el = card.cloneNode(true);
            el.className = 'card drag-ghost';
            el.style.width = rect.width + 'px';
            el.style.left = '0px';
            el.style.top = '0px';
            el.style.padding = getComputedStyle(card).padding;
            document.body.appendChild(el);

            // Initialize position at card's current location
            ghostPos.x = rect.left;
            ghostPos.y = rect.top;
            targetPos.x = rect.left;
            targetPos.y = rect.top;
            lastFrameTime = 0;

            // Set initial transform
            el.style.transform = `translate3d(${ghostPos.x}px, ${ghostPos.y}px, 0) scale(1.02) rotate(0deg)`;

            // Fade in smoothly
            requestAnimationFrame(() => {
                el.classList.add('visible');
                animationId = requestAnimationFrame(animateGhost);
            });

            return el;
        }

        function updatePlaceholder(colBody, y) {
            // Remove old placeholder
            if (placeholder) {
                placeholder.classList.remove('visible');
            }

            // Create or reuse placeholder
            if (!placeholder || !placeholder.parentNode) {
                placeholder = document.createElement('div');
                placeholder.className = 'drop-placeholder';
            }

            const cards = Array.from(colBody.querySelectorAll('.card:not(.is-dragging)'));
            let insertBefore = null;

            for (const c of cards) {
                const rect = c.getBoundingClientRect();
                if (y < rect.top + rect.height / 2) {
                    insertBefore = c;
                    break;
                }
            }

            if (insertBefore) {
                colBody.insertBefore(placeholder, insertBefore);
            } else {
                colBody.appendChild(placeholder);
            }

            // Animate in
            requestAnimationFrame(() => {
                placeholder.classList.add('visible');
            });
        }

        function cleanup(animate = true, dropTarget = null) {
            if (animationId) {
                cancelAnimationFrame(animationId);
                animationId = null;
            }
            lastFrameTime = 0;

            if (drag && drag.card) {
                drag.card.classList.remove('is-dragging');
            }

            document.body.classList.remove('is-dragging');
            document.querySelectorAll('.column').forEach(c => c.classList.remove('drag-over'));

            if (placeholder) {
                placeholder.classList.remove('visible');
                setTimeout(() => {
                    if (placeholder && placeholder.parentNode) {
                        placeholder.remove();
                    }
                    placeholder = null;
                }, 120);
            }

            if (ghost) {
                if (animate && dropTarget) {
                    // Smooth snap to drop zone
                    const targetRect = dropTarget.getBoundingClientRect();
                    ghost.style.transition = 'transform 0.18s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.12s ease 0.06s';
                    ghost.style.transform = `translate3d(${targetRect.left + 8}px, ${targetRect.top + 8}px, 0) scale(0.96) rotate(0deg)`;
                    ghost.style.opacity = '0';
                    setTimeout(() => {
                        if (ghost) ghost.remove();
                        ghost = null;
                    }, 200);
                } else if (animate) {
                    // Snap back animation
                    ghost.style.transition = 'transform 0.15s ease-out, opacity 0.1s ease';
                    ghost.style.transform = `translate3d(${ghostPos.x}px, ${ghostPos.y}px, 0) scale(0.95) rotate(0deg)`;
                    ghost.style.opacity = '0';
                    setTimeout(() => {
                        if (ghost) ghost.remove();
                        ghost = null;
                    }, 150);
                } else {
                    ghost.remove();
                    ghost = null;
                }
            }

            drag = null;
        }

        async function handleDrop(x, y) {
            // Get element under cursor (ghost has pointer-events: none)
            const target = document.elementFromPoint(x, y);
            const colBody = target ? target.closest('.column-body') : null;

            if (!colBody || !drag) return { success: false, target: null };

            const targetCol = colBody.closest('.column');
            const targetStatus = targetCol.dataset.status;
            if (targetStatus === 'quotes') return { success: false, target: null };

            const sourceCol = drag.card.closest('.column');

            try {
                let response, data;
                if (drag.type === 'quote') {
                    response = await fetch('/api/quote/to-post', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({quote_id: drag.id, status: targetStatus})
                    });
                    data = await response.json();
                } else {
                    response = await fetch('/api/post/status', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({post_id: drag.id, status: targetStatus})
                    });
                    data = await response.json();
                }

                if (response.ok) {
                    // Seamless DOM update - no page reload!
                    if (drag.type === 'quote') {
                        // Quote converted to post - remove from quotes, will appear on next refresh
                        // For now just remove the card smoothly
                        drag.card.style.transition = 'opacity 0.2s, transform 0.2s';
                        drag.card.style.opacity = '0';
                        drag.card.style.transform = 'scale(0.9)';
                        setTimeout(() => drag.card.remove(), 200);
                        showToast('Post created!');
                        // Store the new post content
                        if (data.post_id && data.content) {
                            POST_CONTENT[data.post_id] = data.content;
                        }
                        // Reload after a moment to show the new post in the right column
                        setTimeout(() => location.reload(), 400);
                    } else {
                        // Move existing post card to new column
                        drag.card.classList.remove('pending', 'approved', 'posted');
                        drag.card.classList.add(targetStatus);

                        // Update status dot
                        const statusDot = drag.card.querySelector('.status-dot');
                        if (statusDot) {
                            statusDot.classList.remove('pending', 'approved', 'posted');
                            statusDot.classList.add(targetStatus);
                        }

                        // Animate card to new position
                        drag.card.style.transition = 'none';
                        drag.card.style.opacity = '0';
                        colBody.appendChild(drag.card);

                        requestAnimationFrame(() => {
                            drag.card.style.transition = 'opacity 0.25s ease, transform 0.25s ease';
                            drag.card.style.opacity = '1';
                            drag.card.style.transform = 'translateY(0)';
                        });

                        // Update column counts
                        updateColumnCount(sourceCol);
                        updateColumnCount(targetCol);

                        showToast('Moved to ' + targetStatus);
                    }
                    return { success: true, target: colBody };
                } else {
                    showToast('Failed to move', true);
                    return { success: false, target: null };
                }
            } catch (err) {
                showToast('Error: ' + err.message, true);
                return { success: false, target: null };
            }
        }

        function updateColumnCount(col) {
            const count = col.querySelectorAll('.card').length;
            const countEl = col.querySelector('.column-count');
            if (countEl) countEl.textContent = count;
        }

        // Pointer events
        document.addEventListener('pointerdown', function(e) {
            if (e.button !== 0) return; // Left click only
            const card = e.target.closest('.card');
            if (!card || e.target.closest('.modal') || e.target.closest('.modal-overlay')) return;

            e.preventDefault();

            const rect = card.getBoundingClientRect();

            drag = {
                card: card,
                type: card.dataset.type,
                id: card.dataset.id,
                startX: e.clientX,
                startY: e.clientY,
                offsetX: e.clientX - rect.left,
                offsetY: e.clientY - rect.top,
                isDragging: false
            };
        }, { passive: false });

        document.addEventListener('pointermove', function(e) {
            if (!drag) return;

            const dx = e.clientX - drag.startX;
            const dy = e.clientY - drag.startY;
            const distance = Math.sqrt(dx * dx + dy * dy);

            // Start dragging
            if (!drag.isDragging && distance > DRAG_THRESHOLD) {
                drag.isDragging = true;
                drag.card.classList.add('is-dragging');
                document.body.classList.add('is-dragging');
                ghost = createGhost(drag.card);
            }

            if (!drag.isDragging) return;

            // Update target position for spring animation
            targetPos.x = e.clientX - drag.offsetX;
            targetPos.y = e.clientY - drag.offsetY;

            // Find drop target
            document.querySelectorAll('.column').forEach(c => c.classList.remove('drag-over'));

            const target = document.elementFromPoint(e.clientX, e.clientY);
            const colBody = target ? target.closest('.column-body') : null;

            if (colBody) {
                const col = colBody.closest('.column');
                const status = col.dataset.status;
                if (status !== 'quotes') {
                    col.classList.add('drag-over');
                    updatePlaceholder(colBody, e.clientY);
                } else if (placeholder) {
                    placeholder.classList.remove('visible');
                }
            } else if (placeholder) {
                placeholder.classList.remove('visible');
            }
        });

        document.addEventListener('pointerup', async function(e) {
            if (!drag) return;

            const wasDragging = drag.isDragging;

            if (wasDragging) {
                const result = await handleDrop(e.clientX, e.clientY);
                cleanup(true, result.target);
            } else {
                openModal(drag.card);
                cleanup(false);
            }
        });

        document.addEventListener('pointercancel', function() {
            cleanup(true);
        });

        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                if (drag) {
                    cleanup(true);
                }
                closeModal();
            }
        });

        // Prevent default drag behavior
        document.addEventListener('dragstart', e => e.preventDefault());
    })();

    // Upload Modal Functions (outside IIFE to be globally accessible)
    let selectedFile = null;

    function openUploadModal() {
        document.getElementById('uploadModal').classList.add('show');
        resetUploadForm();
    }

    function closeUploadModal() {
        document.getElementById('uploadModal').classList.remove('show');
        resetUploadForm();
    }

    function resetUploadForm() {
        selectedFile = null;
        document.getElementById('uploadForm').style.display = 'block';
        document.getElementById('uploadProcessing').classList.remove('show');
        document.getElementById('uploadResult').classList.remove('show');
        document.getElementById('fileInfo').classList.remove('show');
        document.getElementById('fileInput').value = '';
        document.getElementById('btnExtract').disabled = true;
    }

    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    function handleFileSelect(file) {
        if (!file) return;

        const ext = file.name.split('.').pop().toLowerCase();
        if (!['pdf', 'docx'].includes(ext)) {
            showToast('Please select a PDF or DOCX file', true);
            return;
        }

        selectedFile = file;
        document.getElementById('fileExt').textContent = ext.toUpperCase();
        document.getElementById('fileName').textContent = file.name;
        document.getElementById('fileSize').textContent = formatFileSize(file.size);
        document.getElementById('fileInfo').classList.add('show');
        document.getElementById('btnExtract').disabled = false;
    }

    function removeFile() {
        selectedFile = null;
        document.getElementById('fileInfo').classList.remove('show');
        document.getElementById('fileInput').value = '';
        document.getElementById('btnExtract').disabled = true;
    }

    async function extractQuotes() {
        if (!selectedFile) return;

        document.getElementById('uploadForm').style.display = 'none';
        document.getElementById('uploadProcessing').classList.add('show');

        const formData = new FormData();
        formData.append('file', selectedFile);

        try {
            const response = await fetch('/api/extract-quotes', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            document.getElementById('uploadProcessing').classList.remove('show');
            document.getElementById('uploadResult').classList.add('show');

            if (response.ok) {
                document.getElementById('resultIcon').className = 'result-icon success';
                document.getElementById('resultIcon').innerHTML = '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>';
                document.getElementById('resultTitle').textContent = 'Quotes Extracted!';
                document.getElementById('resultExtracted').textContent = data.extracted || 0;
                document.getElementById('resultSaved').textContent = data.saved || 0;
            } else {
                document.getElementById('resultIcon').className = 'result-icon error';
                document.getElementById('resultIcon').innerHTML = '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M18 6L6 18M6 6l12 12"/></svg>';
                document.getElementById('resultTitle').textContent = data.error || 'Extraction failed';
                document.getElementById('resultExtracted').textContent = '0';
                document.getElementById('resultSaved').textContent = '0';
            }
        } catch (err) {
            document.getElementById('uploadProcessing').classList.remove('show');
            document.getElementById('uploadResult').classList.add('show');
            document.getElementById('resultIcon').className = 'result-icon error';
            document.getElementById('resultIcon').innerHTML = '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M18 6L6 18M6 6l12 12"/></svg>';
            document.getElementById('resultTitle').textContent = 'Connection error';
            document.getElementById('resultExtracted').textContent = '0';
            document.getElementById('resultSaved').textContent = '0';
        }
    }

    function finishUpload() {
        closeUploadModal();
        location.reload();
    }

    // Generate consistent color from source name
    function getSourceColor(source) {
        let hash = 0;
        for (let i = 0; i < source.length; i++) {
            hash = source.charCodeAt(i) + ((hash << 5) - hash);
        }

        // Generate pleasant, distinct hues avoiding muddy colors
        const hue = Math.abs(hash) % 360;
        const saturation = 65 + (Math.abs(hash >> 8) % 20);
        const lightness = 55 + (Math.abs(hash >> 16) % 15);

        return {
            bg: `hsla(${hue}, ${saturation}%, ${lightness}%, 0.15)`,
            text: `hsl(${hue}, ${saturation}%, ${lightness}%)`
        };
    }

    // Apply colors to all source tags
    function applySourceColors() {
        document.querySelectorAll('.tag-source[data-source]').forEach(tag => {
            const source = tag.dataset.source;
            if (source) {
                const colors = getSourceColor(source);
                tag.style.backgroundColor = colors.bg;
                tag.style.color = colors.text;
            }
        });
    }

    // Shuffle cards with animation
    function shuffleCards() {
        const btn = document.querySelector('.btn-shuffle');
        const colBody = document.querySelector('.col-quotes .column-body');
        const cards = Array.from(colBody.querySelectorAll('.card'));

        if (cards.length < 2) return;

        // Add spinning animation to button
        btn.classList.add('shuffling');

        // Fade out cards
        cards.forEach(card => {
            card.style.transition = 'opacity 0.15s ease, transform 0.15s ease';
            card.style.opacity = '0.3';
            card.style.transform = 'scale(0.95)';
        });

        setTimeout(() => {
            // Fisher-Yates shuffle
            for (let i = cards.length - 1; i > 0; i--) {
                const j = Math.floor(Math.random() * (i + 1));
                [cards[i], cards[j]] = [cards[j], cards[i]];
            }

            // Reorder in DOM
            cards.forEach((card, index) => {
                card.style.transitionDelay = `${index * 30}ms`;
                colBody.appendChild(card);
            });

            // Fade back in with stagger
            requestAnimationFrame(() => {
                cards.forEach((card, index) => {
                    card.style.transitionDelay = `${index * 40}ms`;
                    card.style.opacity = '1';
                    card.style.transform = 'scale(1)';
                });
            });

            // Cleanup
            setTimeout(() => {
                cards.forEach(card => {
                    card.style.transition = '';
                    card.style.transitionDelay = '';
                });
                btn.classList.remove('shuffling');
            }, 500);
        }, 150);
    }

    // File input and drag-drop handlers
    document.addEventListener('DOMContentLoaded', function() {
        // Apply source colors on load
        applySourceColors();
        const uploadZone = document.getElementById('uploadZone');
        const fileInput = document.getElementById('fileInput');

        uploadZone.addEventListener('click', () => fileInput.click());

        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length) handleFileSelect(e.target.files[0]);
        });

        uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadZone.classList.add('drag-over');
        });

        uploadZone.addEventListener('dragleave', () => {
            uploadZone.classList.remove('drag-over');
        });

        uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadZone.classList.remove('drag-over');
            if (e.dataTransfer.files.length) handleFileSelect(e.dataTransfer.files[0]);
        });

        // Close modal on backdrop click
        document.getElementById('uploadModal').addEventListener('click', (e) => {
            if (e.target.id === 'uploadModal') closeUploadModal();
        });

        // Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && document.getElementById('uploadModal').classList.contains('show')) {
                closeUploadModal();
            }
        });
    });
    </script>
</body>
</html>
"""


@app.route('/')
def dashboard():
    init_db()
    session = get_session()

    fresh_quotes = session.query(Quote).filter(
        Quote.approved == True,
        Quote.used_count == 0
    ).order_by(Quote.quality_score.desc()).all()

    approved_posts = session.query(Post).filter(
        Post.status == PostStatus.APPROVED.value
    ).order_by(Post.scheduled_time.asc()).all()

    pending_posts = session.query(Post).filter(
        Post.status == PostStatus.PENDING.value
    ).order_by(Post.scheduled_time.asc()).all()

    posted_posts = session.query(Post).filter(
        Post.status == PostStatus.POSTED.value
    ).order_by(Post.posted_time.desc()).limit(20).all()

    stats = {
        'total_quotes': session.query(Quote).count(),
        'documents': session.query(Quote.source).distinct().count(),
        'unused_quotes': session.query(Quote).filter(Quote.used_count == 0).count(),
        'posted': session.query(Post).filter(Post.status == PostStatus.POSTED.value).count(),
    }

    return render_template_string(
        DASHBOARD_TEMPLATE,
        fresh_quotes=fresh_quotes,
        approved_posts=approved_posts,
        pending_posts=pending_posts,
        posted_posts=posted_posts,
        stats=stats
    )


@app.route('/api/post/status', methods=['POST'])
def update_post_status():
    data = request.json
    post_id = data.get('post_id')
    new_status = data.get('status')

    if not post_id or new_status not in ['pending', 'approved', 'posted']:
        return jsonify({'error': 'Invalid request'}), 400

    session = get_session()
    post = session.query(Post).filter(Post.id == post_id).first()
    if not post:
        return jsonify({'error': 'Post not found'}), 404

    post.status = new_status
    if new_status == 'approved':
        post.approved_at = datetime.now(UTC)
    elif new_status == 'posted':
        post.posted_time = datetime.now(UTC)

    session.commit()
    return jsonify({'success': True})


@app.route('/api/quote/to-post', methods=['POST'])
def quote_to_post():
    data = request.json
    quote_id = data.get('quote_id')
    status = data.get('status', 'pending')

    if not quote_id:
        return jsonify({'error': 'Missing quote_id'}), 400

    session = get_session()
    quote = session.query(Quote).filter(Quote.id == quote_id).first()
    if not quote:
        return jsonify({'error': 'Quote not found'}), 404

    hashtags = "#EdgeOfICT #ICTTrading"
    content = f'"{quote.content}"\n\nTrack your edge.\n\n{hashtags}'
    if len(content) > 280:
        max_len = 280 - len(f'"\n\nTrack your edge.\n\n{hashtags}') - 6
        content = f'"{quote.content[:max_len]}..."\n\nTrack your edge.\n\n{hashtags}'

    post = Post(
        quote_id=quote.id,
        platform="twitter",
        content=content,
        status=status,
        created_at=datetime.now(UTC)
    )
    if status == 'approved':
        post.approved_at = datetime.now(UTC)

    quote.used_count += 1
    session.add(post)
    session.commit()

    return jsonify({'success': True, 'post_id': post.id, 'content': content})


@app.route('/api/extract-quotes', methods=['POST'])
def extract_quotes_from_upload():
    import os
    import tempfile

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in ['pdf', 'docx']:
        return jsonify({'error': 'Invalid file type. Use PDF or DOCX'}), 400

    try:
        from core.content_extractor import ContentExtractor

        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{ext}') as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        try:
            extractor = ContentExtractor()
            extracted, saved = extractor.extract_and_save(tmp_path)
            return jsonify({
                'success': True,
                'extracted': extracted,
                'saved': saved
            })
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    except ValueError as e:
        if 'GROQ_API_KEY' in str(e):
            return jsonify({'error': 'API key not configured. Set GROQ_API_KEY environment variable.'}), 500
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': f'Extraction failed: {str(e)}'}), 500


def ensure_db_seeded():
    """Seed sample data if database is empty."""
    init_db()
    session = get_session()
    if session.query(Quote).count() == 0:
        from seed_sample_data import seed_quotes, seed_posts
        seed_quotes()
        seed_posts()
        print("Database seeded with sample data")

# Seed on import for production (gunicorn)
ensure_db_seeded()

if __name__ == '__main__':
    print("\n  EdgeOfICT Kanban: http://localhost:5001\n")
    app.run(debug=True, port=5001)
