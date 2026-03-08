"""
Evidence mapper for linking AI claims to source database records.

This module provides the EvidenceMapper class that extracts claims from
LLM responses and matches them to evidence cards based on content similarity.
This enables traceability from AI-generated insights back to the underlying data.

Requirements: 4.1.4
"""

from typing import List, Dict, Any
from pydantic import BaseModel


class EvidenceMapper:
    """
    Maps AI claims to source evidence cards.
    
    The EvidenceMapper extracts specific claims from LLM responses and
    associates them with relevant evidence cards based on content similarity.
    This provides traceability between AI assessments and source data.
    
    Requirements: 4.1.4
    """
    
    def map_claims_to_evidence(
        self,
        response: BaseModel,
        retrieved_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Map claims from LLM response to evidence cards.
        
        Extracts claims from the response text and matches them to evidence
        cards based on content similarity. Each claim is associated with
        relevant evidence cards that support it.
        
        Args:
            response: LLM response as a Pydantic BaseModel (e.g., WeeklyEvalContract)
            retrieved_data: List of retrieved data dictionaries with evidence cards
            
        Returns:
            List of evidence card dictionaries with fields:
                - claim_text: The specific claim from the AI response
                - source_type: Type of source (activity/goal/metric/log)
                - source_id: Database record ID
                - source_date: ISO format date
                - relevance_score: Float 0.0-1.0
        
        Requirements: 4.1.4
        """
        # Extract claims from response
        claims = self._extract_claims(response)
        
        # Match claims to evidence cards
        evidence_cards = []
        for claim in claims:
            matching_cards = self._find_matching_evidence(claim, retrieved_data)
            evidence_cards.extend(matching_cards)
        
        # Remove duplicates (same source_id + source_type)
        evidence_cards = self._deduplicate_evidence(evidence_cards)
        
        return evidence_cards
    
    def _extract_claims(self, response: BaseModel) -> List[str]:
        """
        Extract specific claims from LLM response.
        
        Extracts claims from various fields in the response model:
        - strengths (list of strings)
        - areas_for_improvement (list of strings)
        - recommendations (list with 'text' field)
        - response_text (for chat responses)
        
        Args:
            response: Pydantic BaseModel containing the LLM response
            
        Returns:
            List of claim strings
        """
        claims = []
        response_dict = response.model_dump()
        
        # Extract from strengths (WeeklyEvalContract)
        if "strengths" in response_dict and response_dict["strengths"]:
            claims.extend(response_dict["strengths"])
        
        # Extract from wins (EvalOutput - legacy schema)
        if "wins" in response_dict and response_dict["wins"]:
            claims.extend(response_dict["wins"])
        
        # Extract from areas_for_improvement (WeeklyEvalContract)
        if "areas_for_improvement" in response_dict and response_dict["areas_for_improvement"]:
            claims.extend(response_dict["areas_for_improvement"])
        
        # Extract from misses (EvalOutput - legacy schema)
        if "misses" in response_dict and response_dict["misses"]:
            claims.extend(response_dict["misses"])
        
        # Extract from recommendations (list of dicts with 'text' or 'action' field)
        if "recommendations" in response_dict and response_dict["recommendations"]:
            for rec in response_dict["recommendations"]:
                if isinstance(rec, dict):
                    # WeeklyEvalContract uses 'text' field
                    if "text" in rec:
                        claims.append(rec["text"])
                    # EvalOutput uses 'action' field
                    elif "action" in rec:
                        claims.append(rec["action"])
                elif isinstance(rec, str):
                    claims.append(rec)
        
        # Extract from response_text (for chat responses)
        if "response_text" in response_dict and response_dict["response_text"]:
            # Split response text into sentences for more granular matching
            response_text = response_dict["response_text"]
            sentences = self._split_into_sentences(response_text)
            claims.extend(sentences)
        
        return claims
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences for claim extraction.
        
        Args:
            text: Text to split
            
        Returns:
            List of sentences
        """
        import re
        # Simple sentence splitting on period, exclamation, question mark
        # followed by space and capital letter
        sentences = re.split(r'[.!?]\s+(?=[A-Z])', text)
        # Filter out very short sentences (< 20 chars)
        return [s.strip() for s in sentences if len(s.strip()) >= 20]
    
    def _find_matching_evidence(
        self,
        claim: str,
        retrieved_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Find evidence cards matching a claim based on content similarity.
        
        Matches claims to evidence cards by checking if the claim references
        keywords related to the evidence type (activity, metric, goal, log).
        
        Args:
            claim: Claim text to match
            retrieved_data: List of retrieved data dictionaries
            
        Returns:
            List of matching evidence card dictionaries (max 3 per claim)
        """
        matches = []
        claim_lower = claim.lower()
        
        for record in retrieved_data:
            # Check if claim references this evidence
            if self._claim_references_evidence(claim_lower, record):
                # Create evidence card
                evidence_card = {
                    "claim_text": claim,
                    "source_type": record.get("type"),
                    "source_id": record.get("id"),
                    "source_date": self._extract_date(record),
                    "relevance_score": self._compute_relevance_score(claim_lower, record)
                }
                matches.append(evidence_card)
        
        # Sort by relevance score and return top 3
        matches.sort(key=lambda x: x["relevance_score"], reverse=True)
        return matches[:3]
    
    def _claim_references_evidence(
        self,
        claim: str,
        record: Dict[str, Any]
    ) -> bool:
        """
        Check if a claim references an evidence record.
        
        Uses keyword matching to determine if the claim is related to
        the evidence record based on its type and content.
        
        Args:
            claim: Claim text (lowercase)
            record: Evidence record dictionary
            
        Returns:
            True if claim references the evidence, False otherwise
        """
        record_type = record.get("type")
        
        # Activity references
        if record_type == "activity":
            activity_keywords = [
                "run", "workout", "activity", "session", "training",
                "exercise", "ride", "swim", "walk", "hike", "bike",
                "distance", "pace", "speed", "duration", "time",
                "heart rate", "hr", "elevation", "climb"
            ]
            # Check for activity type match
            activity_type = record.get("activity_type", "").lower()
            if activity_type and activity_type in claim:
                return True
            # Check for general activity keywords
            if any(kw in claim for kw in activity_keywords):
                return True
        
        # Metric references
        elif record_type == "metric":
            metric_keywords = [
                "weight", "body fat", "waist", "rhr", "resting heart rate",
                "sleep", "measurement", "metric", "body composition",
                "energy", "recovery"
            ]
            if any(kw in claim for kw in metric_keywords):
                return True
        
        # Goal references
        elif record_type == "goal":
            goal_keywords = [
                "goal", "target", "objective", "aim", "plan",
                "marathon", "race", "event", "competition",
                "progress", "on track", "achievement"
            ]
            # Check for goal type match
            goal_type = record.get("goal_type", "").lower()
            if goal_type and goal_type in claim:
                return True
            # Check for general goal keywords
            if any(kw in claim for kw in goal_keywords):
                return True
        
        # Log references
        elif record_type == "log":
            log_keywords = [
                "nutrition", "calories", "protein", "carbs", "fat",
                "diet", "eating", "food", "meal", "macro",
                "adherence", "fasting"
            ]
            if any(kw in claim for kw in log_keywords):
                return True
        
        return False
    
    def _compute_relevance_score(
        self,
        claim: str,
        record: Dict[str, Any]
    ) -> float:
        """
        Compute relevance score for a claim-evidence pair.
        
        Scores are based on:
        - Exact matches (activity type, goal type): 1.0
        - Multiple keyword matches: 0.9
        - Single keyword match: 0.7
        - Default: 0.5
        
        Args:
            claim: Claim text (lowercase)
            record: Evidence record dictionary
            
        Returns:
            Relevance score between 0.0 and 1.0
        """
        record_type = record.get("type")
        
        # Check for exact type matches
        if record_type == "activity":
            activity_type = record.get("activity_type", "").lower()
            if activity_type and activity_type in claim:
                return 1.0
        elif record_type == "goal":
            goal_type = record.get("goal_type", "").lower()
            if goal_type and goal_type in claim:
                return 1.0
        
        # Count keyword matches
        keyword_count = 0
        
        if record_type == "activity":
            keywords = ["run", "workout", "activity", "training", "distance", "pace", "heart rate"]
        elif record_type == "metric":
            keywords = ["weight", "body fat", "rhr", "sleep", "metric"]
        elif record_type == "goal":
            keywords = ["goal", "target", "progress", "marathon", "race"]
        elif record_type == "log":
            keywords = ["nutrition", "calories", "protein", "diet"]
        else:
            keywords = []
        
        keyword_count = sum(1 for kw in keywords if kw in claim)
        
        # Score based on keyword count
        if keyword_count >= 3:
            return 0.9
        elif keyword_count >= 1:
            return 0.7
        else:
            return 0.5
    
    def _extract_date(self, record: Dict[str, Any]) -> str:
        """
        Extract date from evidence record.
        
        Different record types store dates in different fields:
        - activity: 'date'
        - metric: 'week_start'
        - log: 'date'
        - goal: 'target_date'
        
        Args:
            record: Evidence record dictionary
            
        Returns:
            ISO format date string
        """
        record_type = record.get("type")
        
        if record_type == "activity":
            return record.get("date", "")
        elif record_type == "metric":
            return record.get("week_start", "")
        elif record_type == "log":
            return record.get("date", "")
        elif record_type == "goal":
            return record.get("target_date", "")
        else:
            return ""
    
    def _deduplicate_evidence(
        self,
        evidence_cards: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate evidence cards.
        
        Two evidence cards are considered duplicates if they have the same
        source_id and source_type. When duplicates are found, keep the one
        with the highest relevance_score.
        
        Args:
            evidence_cards: List of evidence card dictionaries
            
        Returns:
            Deduplicated list of evidence cards
        """
        seen = {}
        
        for card in evidence_cards:
            key = (card["source_id"], card["source_type"])
            
            # If not seen before, add it
            if key not in seen:
                seen[key] = card
            else:
                # If seen before, keep the one with higher relevance score
                if card["relevance_score"] > seen[key]["relevance_score"]:
                    seen[key] = card
        
        return list(seen.values())
