import io
import json
import zipfile
import logging
from typing import Dict, Any, List, Optional
from django.conf import settings
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.accounts.models import User
from .models import (
    Question,
    QuestionVersion,
    QuestionType,
    Difficulty,
    CodingLanguage,
    VersionStatus,
)
from .services import QuestionService

logger = logging.getLogger(__name__)


class HackerRankQuestionImporter:
    """
    Authorized HackerRank API question importer.
    Strict security policy:
    - Never uses web scraping, crawling, or private/undocumented web endpoints.
    - Operates strictly through authorized account API credentials.
    """

    @classmethod
    def is_configured(cls) -> bool:
        token = getattr(settings, 'HACKERRANK_API_TOKEN', '') or ''
        return bool(token.strip())

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        configured = cls.is_configured()
        return {
            "configured": configured,
            "auth_mode": "BEARER_TOKEN" if configured else "UNCONFIGURED",
            "message": "HackerRank official integration active" if configured else "HackerRank integration not configured. Provide API credentials or use manual import."
        }

    @classmethod
    def import_by_slug_or_data(cls, slug_or_id: str = "", payload_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        data = payload_data or {}
        has_content = bool(data.get('body') or data.get('problem_statement') or data.get('description'))

        if not cls.is_configured() and not has_content:
            raise DRFValidationError({
                "hackerrank": "HackerRank authorized integration is not configured. Configure HACKERRANK_API_TOKEN or import via structured content."
            })

        # Normalize into CODEGUARD schema
        title = data.get('name') or data.get('title') or (slug_or_id.replace('-', ' ').title() if slug_or_id else "Imported HackerRank Problem")
        problem_text = data.get('body') or data.get('problem_statement') or data.get('description') or ""
        constraints = data.get('constraints') or ""
        input_format = data.get('input_format') or ""
        output_format = data.get('output_format') or ""
        
        diff_raw = (data.get('difficulty') or 'MEDIUM').upper()
        difficulty = diff_raw if diff_raw in ['EASY', 'MEDIUM', 'HARD'] else 'MEDIUM'

        raw_languages = data.get('languages') or ['python3', 'cpp20', 'java17']
        allowed_languages = []
        for l in raw_languages:
            l_up = str(l).upper()
            if 'PYTHON' in l_up and CodingLanguage.PYTHON not in allowed_languages:
                allowed_languages.append(CodingLanguage.PYTHON)
            elif ('CPP' in l_up or 'C++' in l_up) and CodingLanguage.CPP not in allowed_languages:
                allowed_languages.append(CodingLanguage.CPP)
            elif 'JAVA' in l_up and CodingLanguage.JAVA not in allowed_languages:
                allowed_languages.append(CodingLanguage.JAVA)
        if not allowed_languages:
            allowed_languages = [CodingLanguage.PYTHON, CodingLanguage.CPP, CodingLanguage.JAVA]

        starter_codes = {}
        if isinstance(data.get('starter_codes'), dict):
            for k, v in data['starter_codes'].items():
                k_norm = 'PYTHON' if 'PYTHON' in str(k).upper() else ('CPP' if 'C' in str(k).upper() else ('JAVA' if 'JAVA' in str(k).upper() else ''))
                if k_norm and k_norm in allowed_languages:
                    starter_codes[k_norm] = str(v)

        examples = []
        if isinstance(data.get('examples'), list):
            for idx, ex in enumerate(data['examples'], start=1):
                examples.append({
                    "input": str(ex.get('input', '')),
                    "output": str(ex.get('output', '')),
                    "explanation": str(ex.get('explanation', f"Sample Example {idx}"))
                })

        test_cases = []
        raw_tests = data.get('test_cases') or []
        for idx, tc in enumerate(raw_tests, start=1):
            test_cases.append({
                "name": tc.get('name') or f"Test Case {idx}",
                "input_data": str(tc.get('input', tc.get('input_data', ''))),
                "expected_output": str(tc.get('output', tc.get('expected_output', ''))),
                "points": max(1, int(tc.get('points', 5))),
                "is_hidden": bool(tc.get('is_hidden', False)),
                "is_verified": False,  # Strict invariant: never automatically verified on import
                "execution_order": idx
            })

        if not test_cases and examples:
            for idx, ex in enumerate(examples, start=1):
                test_cases.append({
                    "name": f"Sample Case {idx}",
                    "input_data": ex['input'],
                    "expected_output": ex['output'],
                    "points": 5,
                    "is_hidden": False,
                    "is_verified": False,
                    "execution_order": idx
                })

        ref_solutions = data.get('reference_solutions') or {}
        ref_lang = data.get('reference_solution_language') or (next(iter(ref_solutions.keys())) if ref_solutions else "")

        return {
            "source": "HACKERRANK",
            "title": title,
            "description": problem_text,
            "difficulty": difficulty,
            "points": sum(tc['points'] for tc in test_cases) if test_cases else 10,
            "tags": data.get('tags', ['hackerrank', 'algorithms']),
            "coding_config": {
                "problem_statement": problem_text,
                "input_description": input_format,
                "output_description": output_format,
                "constraints": constraints,
                "allowed_languages": allowed_languages,
                "starter_codes": starter_codes,
                "examples": examples,
                "reference_solutions": ref_solutions,
                "reference_solution_language": ref_lang,
                "reference_solution_verified": False,
                "time_limit_ms": min(5000, max(500, int(data.get('time_limit_ms', 2000)))),
                "memory_limit_mb": min(512, max(64, int(data.get('memory_limit_mb', 256)))),
            },
            "test_cases": test_cases
        }


class LeetCodeManualImporter:
    """
    LeetCode Structured / Manual Importer.
    Strict compliance policy:
    - LeetCode's Terms prohibit crawling, scraping, and unauthorized spidering.
    - This importer operates STRICTLY on administrator-provided structured content,
      JSON exports, or manual text, NEVER through automated scraping.
    """

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        return {
            "configured": False,
            "auth_mode": "MANUAL_IMPORT_REQUIRED",
            "message": "LeetCode terms prohibit automated scraping. Import via pasted content or structured files."
        }

    @classmethod
    def import_structured_content(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        if 'url' in payload and not payload.get('problem_statement') and not payload.get('content'):
            raise DRFValidationError({
                "leetcode": "Direct web URL scraping of LeetCode is prohibited by Terms of Service. Please paste question content or upload a structured export."
            })

        title = payload.get('title') or "Imported LeetCode Problem"
        problem_text = payload.get('problem_statement') or payload.get('content') or payload.get('description') or ""
        constraints = payload.get('constraints') or ""
        input_format = payload.get('input_format') or ""
        output_format = payload.get('output_format') or ""

        diff_raw = (payload.get('difficulty') or 'MEDIUM').upper()
        difficulty = diff_raw if diff_raw in ['EASY', 'MEDIUM', 'HARD'] else 'MEDIUM'

        allowed_languages = [CodingLanguage.PYTHON, CodingLanguage.CPP, CodingLanguage.JAVA]
        starter_codes = payload.get('starter_codes') or {}

        examples = []
        if isinstance(payload.get('examples'), list):
            for idx, ex in enumerate(payload['examples'], start=1):
                examples.append({
                    "input": str(ex.get('input', '')),
                    "output": str(ex.get('output', '')),
                    "explanation": str(ex.get('explanation', f"Example {idx}"))
                })

        test_cases = []
        raw_tests = payload.get('test_cases') or []
        for idx, tc in enumerate(raw_tests, start=1):
            test_cases.append({
                "name": tc.get('name') or f"Case {idx}",
                "input_data": str(tc.get('input', tc.get('input_data', ''))),
                "expected_output": str(tc.get('output', tc.get('expected_output', ''))),
                "points": max(1, int(tc.get('points', 5))),
                "is_hidden": bool(tc.get('is_hidden', False)),
                "is_verified": False,
                "execution_order": idx
            })

        if not test_cases and examples:
            for idx, ex in enumerate(examples, start=1):
                test_cases.append({
                    "name": f"Example Case {idx}",
                    "input_data": ex['input'],
                    "expected_output": ex['output'],
                    "points": 5,
                    "is_hidden": False,
                    "is_verified": False,
                    "execution_order": idx
                })

        return {
            "source": "LEETCODE_MANUAL",
            "title": title,
            "description": problem_text,
            "difficulty": difficulty,
            "points": sum(tc['points'] for tc in test_cases) if test_cases else 10,
            "tags": payload.get('tags', ['leetcode', 'algorithms']),
            "coding_config": {
                "problem_statement": problem_text,
                "input_description": input_format,
                "output_description": output_format,
                "constraints": constraints,
                "allowed_languages": allowed_languages,
                "starter_codes": starter_codes,
                "examples": examples,
                "reference_solutions": payload.get('reference_solutions', {}),
                "reference_solution_language": payload.get('reference_solution_language', ''),
                "reference_solution_verified": False,
                "time_limit_ms": 2000,
                "memory_limit_mb": 256,
            },
            "test_cases": test_cases
        }


class PackageZipImporter:
    """
    Standard CODEGUARD ZIP / Structured Package Importer.
    Expects a ZIP archive with:
    - question.json (metadata, problem, config, test cases)
    - or problem.md + metadata.json + testcases/
    """

    @classmethod
    def import_zip_file(cls, zip_bytes: bytes) -> Dict[str, Any]:
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
                file_list = zf.namelist()
                
                # Check for question.json
                q_json_path = next((f for f in file_list if f.endswith('question.json')), None)
                if q_json_path:
                    data = json.loads(zf.read(q_json_path).decode('utf-8'))
                    return cls._normalize_package_data(data, zf, file_list)

                # Fallback: check for metadata.json + problem.md
                meta_path = next((f for f in file_list if f.endswith('metadata.json')), None)
                prob_path = next((f for f in file_list if f.endswith('problem.md') or f.endswith('README.md')), None)
                
                if meta_path and prob_path:
                    data = json.loads(zf.read(meta_path).decode('utf-8'))
                    data['problem_statement'] = zf.read(prob_path).decode('utf-8')
                    return cls._normalize_package_data(data, zf, file_list)

                raise DRFValidationError({
                    "zip_file": "ZIP archive must contain 'question.json' or 'metadata.json' and 'problem.md'."
                })
        except zipfile.BadZipFile:
            raise DRFValidationError({"zip_file": "Uploaded file is not a valid ZIP archive."})
        except json.JSONDecodeError:
            raise DRFValidationError({"zip_file": "Package JSON file contains invalid syntax."})

    @classmethod
    def _normalize_package_data(cls, data: Dict[str, Any], zf: zipfile.ZipFile, file_list: List[str]) -> Dict[str, Any]:
        title = data.get('title') or "Imported Package Problem"
        problem_statement = data.get('problem_statement') or data.get('description') or ""
        diff_raw = (data.get('difficulty') or 'MEDIUM').upper()
        difficulty = diff_raw if diff_raw in ['EASY', 'MEDIUM', 'HARD'] else 'MEDIUM'

        allowed_langs = [CodingLanguage.PYTHON, CodingLanguage.CPP, CodingLanguage.JAVA]
        if data.get('allowed_languages'):
            allowed_langs = [l for l in data['allowed_languages'] if l in [CodingLanguage.PYTHON, CodingLanguage.CPP, CodingLanguage.JAVA]]

        test_cases = []
        # Check if test cases are defined in JSON
        if data.get('test_cases') and isinstance(data['test_cases'], list):
            for idx, tc in enumerate(data['test_cases'], start=1):
                test_cases.append({
                    "name": tc.get('name') or f"Case {idx}",
                    "input_data": str(tc.get('input_data', tc.get('input', ''))),
                    "expected_output": str(tc.get('expected_output', tc.get('output', ''))),
                    "points": max(1, int(tc.get('points', 5))),
                    "is_hidden": bool(tc.get('is_hidden', False)),
                    "is_verified": False,
                    "execution_order": idx
                })

        # Check for test cases directory: testcases/in_*.txt, testcases/out_*.txt
        in_files = sorted([f for f in file_list if '/in' in f or f.startswith('in') or 'input' in f])
        if not test_cases and in_files:
            idx = 1
            for in_f in in_files:
                out_f = in_f.replace('in', 'out').replace('input', 'output')
                if out_f in file_list:
                    in_content = zf.read(in_f).decode('utf-8')
                    out_content = zf.read(out_f).decode('utf-8')
                    test_cases.append({
                        "name": f"File Test {idx}",
                        "input_data": in_content,
                        "expected_output": out_content,
                        "points": 5,
                        "is_hidden": idx > 2,  # First 2 sample, rest hidden
                        "is_verified": False,
                        "execution_order": idx
                    })
                    idx += 1

        return {
            "source": "CODEGUARD_ZIP",
            "title": title,
            "description": problem_statement,
            "difficulty": difficulty,
            "points": sum(tc['points'] for tc in test_cases) if test_cases else 10,
            "tags": data.get('tags', ['imported-package']),
            "coding_config": {
                "problem_statement": problem_statement,
                "input_description": data.get('input_format', ''),
                "output_description": data.get('output_format', ''),
                "constraints": data.get('constraints', ''),
                "allowed_languages": allowed_langs,
                "starter_codes": data.get('starter_codes', {}),
                "examples": data.get('examples', []),
                "reference_solutions": data.get('reference_solutions', {}),
                "reference_solution_language": data.get('reference_solution_language', ''),
                "reference_solution_verified": False,
                "time_limit_ms": min(5000, max(500, int(data.get('time_limit_ms', 2000)))),
                "memory_limit_mb": min(512, max(64, int(data.get('memory_limit_mb', 256)))),
            },
            "test_cases": test_cases
        }


class PlatformImportService:
    """
    Coordinator domain service for all platform imports.
    Enforces invariant: All imported questions are created in DRAFT status,
    with unverified expected outputs and full Question Health gating.
    """

    @classmethod
    def get_platforms_status(cls) -> Dict[str, Any]:
        return {
            "hackerrank": HackerRankQuestionImporter.get_status(),
            "leetcode": LeetCodeManualImporter.get_status(),
            "zip_package": {
                "supported": True,
                "auth_mode": "DIRECT_UPLOAD",
                "message": "Upload standard question definition ZIP archive"
            },
            "manual_json": {
                "supported": True,
                "auth_mode": "PASTE_JSON",
                "message": "Paste structured problem definition"
            }
        }

    @classmethod
    def parse_preview(cls, source: str, payload_data: Dict[str, Any], file_bytes: Optional[bytes] = None) -> Dict[str, Any]:
        src_upper = (source or '').upper()

        if src_upper == 'HACKERRANK':
            normalized = HackerRankQuestionImporter.import_by_slug_or_data(
                slug_or_id=payload_data.get('slug', ''),
                payload_data=payload_data.get('data') or payload_data
            )
        elif src_upper == 'LEETCODE' or src_upper == 'LEETCODE_MANUAL':
            normalized = LeetCodeManualImporter.import_structured_content(payload_data)
        elif src_upper == 'CODEGUARD_ZIP' or src_upper == 'ZIP':
            if not file_bytes:
                raise DRFValidationError({"file": "ZIP file required for package import."})
            normalized = PackageZipImporter.import_zip_file(file_bytes)
        elif src_upper == 'MANUAL_JSON':
            normalized = LeetCodeManualImporter.import_structured_content(payload_data)
        else:
            raise DRFValidationError({"source": f"Unsupported platform source: {source}"})

        # Generate preview metadata
        test_cases = normalized.get('test_cases', [])
        sample_count = len([tc for tc in test_cases if not tc.get('is_hidden')])
        hidden_count = len([tc for tc in test_cases if tc.get('is_hidden')])
        ref_sol = normalized.get('coding_config', {}).get('reference_solutions', {})

        return {
            "source": normalized['source'],
            "title": normalized['title'],
            "difficulty": normalized['difficulty'],
            "tags": normalized.get('tags', []),
            "languages": normalized['coding_config']['allowed_languages'],
            "examples": normalized['coding_config'].get('examples', []),
            "test_case_count": len(test_cases),
            "sample_test_count": sample_count,
            "hidden_test_count": hidden_count,
            "has_reference_solution": bool(ref_sol),
            "reference_solution_language": normalized['coding_config'].get('reference_solution_language', ''),
            "expected_output_verification_status": "UNVERIFIED",
            "import_status": "DRAFT",
            "normalized_payload": normalized
        }

    @classmethod
    def confirm_and_create_draft(cls, normalized_payload: Dict[str, Any], actor: User, request=None) -> QuestionVersion:
        """
        Creates the imported question in DRAFT status with full audit trail.
        """
        if not normalized_payload:
            raise DRFValidationError({"payload": "Normalized payload cannot be empty."})

        # Enforce DRAFT status and unverified test cases
        coding_config = normalized_payload.get('coding_config', {})
        test_cases = normalized_payload.get('test_cases', [])

        for tc in test_cases:
            tc['is_verified'] = False

        coding_config['reference_solution_verified'] = False
        coding_config['reference_solution_verified_at'] = None

        question, version = QuestionService.create_question(
            question_type=QuestionType.CODING,
            title=normalized_payload['title'],
            description=normalized_payload.get('description', ''),
            instructions=normalized_payload.get('instructions', ''),
            points=normalized_payload.get('points', 10),
            negative_marking_enabled=normalized_payload.get('negative_marking_enabled', False),
            negative_points=normalized_payload.get('negative_points', 0),
            difficulty=normalized_payload.get('difficulty', Difficulty.MEDIUM),
            tags=normalized_payload.get('tags', []),
            coding_config_data=coding_config,
            test_cases_data=test_cases,
            actor=actor,
            request=request
        )

        return version
