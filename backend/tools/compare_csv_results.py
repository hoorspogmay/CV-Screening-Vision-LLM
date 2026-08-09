import csv
import sys
from pathlib import Path

# Ensure repo packages are importable when running this script directly.
backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from app.schemas import ResumeResult, Decision
from app.resume_service import _finalize_result
from app.resume_service import _route_resume_to_job_profiles
from app.job_requirements import JobOpeningProfile, JobRequirements
from app.resume_service import _expand_routing_terms, _normalize_routing_text


def parse_bool(val: str):
    if val is None or val == "":
        return None
    v = val.strip().lower()
    if v in ("true", "1", "yes"):
        return True
    if v in ("false", "0", "no"):
        return False
    return None


def load_ground_truth(path: Path):
    gt = {}
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            fname = r.get("CV Filename") or r.get("Filename") or r.get("File Name")
            if not fname:
                continue
            gt[fname.strip()] = r
    return gt


def main(screening_csv: Path, ground_truth_csv: Path):
    ground = load_ground_truth(ground_truth_csv)
    rows = []
    with screening_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    report = []
    for r in rows:
        file_name = r.get("File Name") or r.get("File") or ""
        candidate = r.get("Candidate Name") or ""
        job_role = r.get("Job Role") or ""
        decision_old = r.get("Decision") or ""
        summary = r.get("Summary") or ""
        match_score = r.get("Match Score")
        try:
            match_score = float(match_score) if match_score not in (None, "") else None
        except Exception:
            match_score = None
        education_level = r.get("Education Level") or None
        exp_years = r.get("Experience Years")
        try:
            exp_years = int(exp_years) if exp_years not in (None, "") else None
        except Exception:
            exp_years = None
        skills_match = parse_bool(r.get("Skills Match") or "")

        rr = ResumeResult(
            file_id=file_name,
            file_name=file_name,
            candidate_name=candidate,
            decision=Decision(decision_old) if decision_old in Decision.__members__.values() or decision_old in [d.value for d in Decision] else Decision.REJECT,
            summary=summary,
            match_score=match_score,
            education_level=education_level,
            experience_years=exp_years,
            skills_match=skills_match,
        )

        new_rr = _finalize_result(rr, None)

        # Perform routing simulation using the ground-truth job set (use screening summary as proxy resume text)
        profiles = []
        job_titles = [g.get("Expected Job") for g in ground.values() if g.get("Expected Job")]
        unique_titles = list(dict.fromkeys(job_titles))
        for job_title in unique_titles:
            profiles.append(JobOpeningProfile(title=job_title, requirements=JobRequirements(job_role=job_title)))

        # Prefer ground-truth reason text as a high-fidelity resume proxy when available
        gt_reason = None
        for k, v in ground.items():
            fname = v.get("CV Filename") or v.get("Filename") or v.get("File Name")
            if fname and fname.strip() == file_name:
                gt_reason = v.get("Ground Truth Reason")
                break
        resume_text_for_routing = gt_reason or summary or ""
        routed, reject_flag = _route_resume_to_job_profiles(resume_text_for_routing, profiles) if profiles else ([], True)
        routed_titles = [p.title for p in routed]

        # Also compute old-style semantic scores for before/after comparison by re-implementing
        # the previous scoring formula so we can show how routing changed.
        def old_semantic_score(resume_text, profile):
            profile_text = " ".join(
                part for part in [
                    profile.title,
                    profile.requirements.job_role,
                    profile.requirements.required_education,
                    " ".join(profile.requirements.required_skills),
                ] if part
            )
            resume_terms = _expand_routing_terms(resume_text)
            profile_terms = _expand_routing_terms(profile_text)
            if not resume_terms or not profile_terms:
                return 0.0
            overlap = len(resume_terms & profile_terms)
            union = len(resume_terms | profile_terms)
            base_score = round(overlap / max(3, union), 3)

            resume_tokens = set(_normalize_routing_text(resume_text).split())
            profile_tokens = set(_normalize_routing_text(profile_text).split())
            title_overlap = len(resume_tokens & profile_tokens)
            skill_overlap = len(
                set(token for token in resume_tokens if token in {"python", "sql", "java", "javascript", "typescript", "react", "node", "fastapi", "django", "postgres", "postgresql", "aws", "azure", "docker", "kubernetes", "tableau", "excel", "powerbi", "graphql", "numpy", "pandas"})
                & set(token for token in profile_tokens if token in {"python", "sql", "java", "javascript", "typescript", "react", "node", "fastapi", "django", "postgres", "postgresql", "aws", "azure", "docker", "kubernetes", "tableau", "excel", "powerbi", "graphql", "numpy", "pandas"})
            )

            weighted_score = base_score + (0.18 * min(2, title_overlap)) + (0.12 * min(3, skill_overlap))
            return round(min(1.0, weighted_score), 3)

        old_selected = []
        new_selected = routed_titles
        old_scores = {p.title: old_semantic_score(resume_text_for_routing or "", p) for p in profiles}
        if old_scores:
            old_best = max(old_scores.items(), key=lambda it: it[1])
            old_selected = [old_best[0]] if old_best[1] >= 0.18 else []
        old_selected_title = old_selected[0] if old_selected else ""
        old_selected_score = old_scores.get(old_selected_title, "") if old_selected_title else ""

        gt = ground.get(file_name)
        expected = None
        if gt is not None:
            expected = gt.get("Expected Decision") or gt.get("Expected Decision")

        report.append({
            "file": file_name,
            "candidate": candidate,
            "old_decision": decision_old,
            "new_decision": new_rr.decision.value,
            "old_score": rr.match_score,
            "new_score": new_rr.match_score,
            "summary_old": rr.summary,
            "summary_new": new_rr.summary,
            "experience_old": rr.experience_years,
            "experience_new": new_rr.experience_years,
            "skills_match_old": rr.skills_match,
            "skills_match_new": new_rr.skills_match,
            "education_old": rr.education_level,
            "education_new": new_rr.education_level,
            "expected_decision": expected,
            "routed_titles": "|".join(routed_titles) if routed_titles else "",
            "routing_reject": reject_flag,
            "old_routed": old_selected_title,
            "old_routed_score": old_selected_score,
        })

    # Print report
    print("file,candidate,old_decision,new_decision,expected_decision,old_score,new_score,experience_old,experience_new,skills_old,skills_new,education_old,education_new,old_routed,old_routed_score,routed_titles,routing_reject")
    for r in report:
        print(
            f"{r['file']},{r['candidate']},{r['old_decision']},{r['new_decision']},{r['expected_decision']},{r['old_score']},{r['new_score']},{r['experience_old']},{r['experience_new']},{r['skills_match_old']},{r['skills_match_new']},{r['education_old']},{r['education_new']},{r.get('old_routed','')},{r.get('old_routed_score','')},{r['routed_titles']},{r['routing_reject']}"
        )


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python compare_csv_results.py <screening_csv> <ground_truth_csv>")
        sys.exit(1)
    screening_csv = Path(sys.argv[1])
    ground_truth_csv = Path(sys.argv[2])
    main(screening_csv, ground_truth_csv)
