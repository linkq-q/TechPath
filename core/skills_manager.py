# 文件用途：Agent Skills 系统管理模块（Phase 4），扫描/加载/匹配/安装技能包

import json
import re
from pathlib import Path

import yaml

from core.database import delete_skill, get_all_skills, save_skill, toggle_skill

# 技能文件根目录
SKILLS_DIR = Path(__file__).parent.parent / "skills"


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """
    解析 .skill.md 文件的 YAML frontmatter。

    Returns:
        (metadata_dict, body_text)
    """
    if not content.startswith("---"):
        return {}, content

    end_idx = content.find("---", 3)
    if end_idx == -1:
        return {}, content

    yaml_str = content[3:end_idx].strip()
    body = content[end_idx + 3:].strip()

    try:
        meta = yaml.safe_load(yaml_str) or {}
    except Exception:
        meta = {}

    return meta, body


def scan_skills_directory(skills_dir: str = None) -> list[dict]:
    """
    扫描 skills 目录下所有 .skill.md 文件，读取 YAML frontmatter。

    Returns:
        技能元数据列表，每条包含 name/description/trigger_keywords/level/file_path
    """
    target_dir = Path(skills_dir) if skills_dir else SKILLS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for skill_file in sorted(target_dir.glob("*.skill.md")):
        try:
            content = skill_file.read_text(encoding="utf-8")
            meta, _ = _parse_frontmatter(content)
            if not meta.get("name"):
                continue
            results.append({
                "name": meta.get("name", ""),
                "description": meta.get("description", ""),
                "trigger_keywords": meta.get("trigger_keywords", []),
                "level": meta.get("level", 1),
                "file_path": str(skill_file),
            })
        except Exception as e:
            print(f"[skills] 解析失败 {skill_file.name}：{e}")

    return results


def load_skill_content(skill_name: str) -> str:
    """
    读取指定 Skill 的完整正文（去掉 YAML frontmatter）。

    Returns:
        Skill 正文 Markdown 文本
    """
    for skill_file in SKILLS_DIR.glob("*.skill.md"):
        try:
            content = skill_file.read_text(encoding="utf-8")
            meta, body = _parse_frontmatter(content)
            if meta.get("name") == skill_name:
                return body
        except Exception:
            continue

    # 也从数据库 content_path 查找
    skills = get_all_skills()
    for s in skills:
        if s["name"] == skill_name and s.get("content_path"):
            p = Path(s["content_path"])
            if p.exists():
                content = p.read_text(encoding="utf-8")
                _, body = _parse_frontmatter(content)
                return body

    return ""


def get_active_skills_context() -> str:
    """
    获取所有激活状态 Skill 的元数据，拼接为可注入系统提示词的文本（Level 1，~100 token/skill）。

    Returns:
        格式化的 Skill 摘要文本
    """
    skills = get_all_skills()
    active = [s for s in skills if s.get("is_active")]
    if not active:
        return ""

    lines = ["## 已激活的技能包 (Agent Skills)\n"]
    for s in active:
        kw = "、".join(s["trigger_keywords"][:5]) if s["trigger_keywords"] else ""
        lines.append(f"- **{s['name']}**：{s['description']}（触发词：{kw}）")
    lines.append("\n当判断用户需求与某个技能包匹配时，可调用 load_skill_detail(skill_name) 加载完整技能内容。")
    return "\n".join(lines)


def match_skill_by_message(message: str) -> list[str]:
    """
    根据用户消息匹配相关 Skill（对比 trigger_keywords）。

    Returns:
        匹配的 Skill 名称列表
    """
    skills = get_all_skills()
    active = [s for s in skills if s.get("is_active")]
    message_lower = message.lower()

    matched = []
    for s in active:
        keywords = s.get("trigger_keywords", [])
        for kw in keywords:
            if kw.lower() in message_lower:
                matched.append(s["name"])
                break

    return matched


def install_skill(
    name: str,
    description: str,
    trigger_keywords: list,
    content: str,
    level: int = 1,
) -> bool:
    """
    将新 Skill 写入 skills/ 目录为 .skill.md 文件，并在数据库中注册。

    Returns:
        是否成功
    """
    try:
        SKILLS_DIR.mkdir(parents=True, exist_ok=True)

        # 生成安全的文件名
        safe_name = re.sub(r"[^\w\-]", "_", name.lower())
        file_path = SKILLS_DIR / f"{safe_name}.skill.md"

        kw_yaml = json.dumps(trigger_keywords, ensure_ascii=False)
        frontmatter = (
            f"---\n"
            f"name: {name}\n"
            f"description: {description}\n"
            f"trigger_keywords: {kw_yaml}\n"
            f"level: {level}\n"
            f"---\n\n"
        )
        file_path.write_text(frontmatter + content, encoding="utf-8")

        meta_json = json.dumps(
            {"name": name, "description": description,
             "trigger_keywords": trigger_keywords, "level": level},
            ensure_ascii=False,
        )
        save_skill(
            name=name,
            description=description,
            trigger_keywords=trigger_keywords,
            content_path=str(file_path),
            metadata_json=meta_json,
            is_active=1,
        )
        return True
    except Exception as e:
        print(f"[skills] 安装失败：{e}")
        return False


def toggle_skill_active(skill_name: str, active: bool) -> bool:
    """启用或禁用指定 Skill（更新数据库 is_active 字段）"""
    return toggle_skill(name=skill_name, is_active=active)


def sync_skills_to_db() -> int:
    """
    扫描 skills/ 目录，将未注册的 Skill 同步到数据库。

    Returns:
        同步的 Skill 数量
    """
    scanned = scan_skills_directory()
    existing = {s["name"] for s in get_all_skills()}
    count = 0
    for s in scanned:
        if s["name"] not in existing:
            meta_json = json.dumps(
                {"name": s["name"], "description": s["description"],
                 "trigger_keywords": s["trigger_keywords"], "level": s["level"]},
                ensure_ascii=False,
            )
            save_skill(
                name=s["name"],
                description=s["description"],
                trigger_keywords=s["trigger_keywords"],
                content_path=s["file_path"],
                metadata_json=meta_json,
                is_active=1,
            )
            count += 1
    return count


print("✅ T05 完成")
