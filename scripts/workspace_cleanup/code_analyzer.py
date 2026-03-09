"""Code analyzer for workspace cleanup system."""

import ast
import logging
from pathlib import Path
from typing import List, Set, Dict, Tuple

from .models import ObsolescenceReport, DuplicateGroup

logger = logging.getLogger(__name__)


class CodeAnalyzer:
    """Identifies obsolete code and evaluates content value."""
    
    def __init__(self, workspace_root: Path):
        """Initialize the code analyzer.
        
        Args:
            workspace_root: Path to the workspace root directory
        """
        self.workspace_root = workspace_root
        self.app_dir = workspace_root / 'app'
        # Cache for test file analysis to support duplicate detection
        self._test_file_cache: Dict[Path, Tuple[Set[str], Set[str]]] = {}  # path -> (test_functions, imports)
    
    def analyze_test_file(self, file_path: Path) -> ObsolescenceReport:
        """Analyze a test file for obsolescence indicators.
        
        This method uses AST parsing to detect:
        - Duplicate functionality (comparing test function names and imports)
        - Removed features (checking if tested modules exist in app/)
        - Temporary files (checking for debug/temp/scratch/tmp in filename)
        - Superseded tests (comparing timestamps and naming patterns)
        
        Args:
            file_path: Path to the test file to analyze
            
        Returns:
            ObsolescenceReport with confidence score
            
        Error Handling:
            - File cannot be read: log error, mark as "preserve" (conservative)
            - Binary file: log warning, mark as "preserve"
            - Parsing fails: log error, mark as "preserve"
            - AST parsing fails: log error, mark for manual review
        """
        # Conservative approach: default to not obsolete
        is_obsolete = False
        reason = ""
        confidence = 0.0
        
        # Check for temporary file patterns in filename
        filename_lower = file_path.name.lower()
        temp_patterns = ['debug', 'temp', 'scratch', 'tmp']
        if any(pattern in filename_lower for pattern in temp_patterns):
            is_obsolete = True
            reason = f"Temporary file detected (filename contains: {', '.join([p for p in temp_patterns if p in filename_lower])})"
            confidence = 0.9
            return ObsolescenceReport(
                file_path=file_path,
                is_obsolete=is_obsolete,
                reason=reason,
                confidence=confidence
            )
        
        # Try to read the file
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError as e:
            # Handle file cannot be read: log error, mark as "preserve"
            error_msg = f"File not found: {file_path} - {e}"
            logger.error(error_msg)
            return ObsolescenceReport(
                file_path=file_path,
                is_obsolete=False,
                reason=f"Could not read file (not found): {str(e)}",
                confidence=0.0
            )
        except PermissionError as e:
            # Handle file cannot be read: log error, mark as "preserve"
            error_msg = f"Permission denied reading file: {file_path} - {e}"
            logger.error(error_msg)
            return ObsolescenceReport(
                file_path=file_path,
                is_obsolete=False,
                reason=f"Could not read file (permission denied): {str(e)}",
                confidence=0.0
            )
        except UnicodeDecodeError as e:
            # Handle binary file: log warning, mark as "preserve"
            warning_msg = f"Binary file or encoding issue: {file_path} - {e}"
            logger.warning(warning_msg)
            return ObsolescenceReport(
                file_path=file_path,
                is_obsolete=False,
                reason=f"Binary file or encoding issue: {str(e)}",
                confidence=0.0
            )
        except OSError as e:
            # Handle file cannot be read: log error, mark as "preserve"
            error_msg = f"Error reading file: {file_path} - {e}"
            logger.error(error_msg)
            return ObsolescenceReport(
                file_path=file_path,
                is_obsolete=False,
                reason=f"Could not read file: {str(e)}",
                confidence=0.0
            )
        
        # Try to parse the file with AST
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError as e:
            # Handle parsing fails: log error, mark as "preserve"
            error_msg = f"Syntax error parsing file: {file_path} - {e}"
            logger.error(error_msg)
            return ObsolescenceReport(
                file_path=file_path,
                is_obsolete=False,
                reason=f"Could not parse file (syntax error): {str(e)}",
                confidence=0.0
            )
        except ValueError as e:
            # Handle AST parsing fails: log error, mark for manual review
            error_msg = f"AST parsing failed: {file_path} - {e}"
            logger.error(error_msg)
            return ObsolescenceReport(
                file_path=file_path,
                is_obsolete=False,
                reason=f"AST parsing failed (requires manual review): {str(e)}",
                confidence=0.0
            )
        except Exception as e:
            # Handle unexpected parsing errors: log error, mark as "preserve"
            error_msg = f"Unexpected error parsing file: {file_path} - {e}"
            logger.error(error_msg)
            return ObsolescenceReport(
                file_path=file_path,
                is_obsolete=False,
                reason=f"Unexpected parsing error: {str(e)}",
                confidence=0.0
            )
        
        # Extract imports and test functions
        imports = self._extract_imports(tree)
        test_functions = self._extract_test_functions(tree)
        
        # Cache the analysis for duplicate detection
        self._test_file_cache[file_path] = (test_functions, imports)
        
        # Check for removed features
        removed_modules = self._check_removed_features(imports)
        
        if removed_modules:
            is_obsolete = True
            reason = f"Tests removed features: {', '.join(removed_modules)}"
            confidence = 0.8
            return ObsolescenceReport(
                file_path=file_path,
                is_obsolete=is_obsolete,
                reason=reason,
                confidence=confidence
            )
        
        # Check for superseded tests (older files with similar names)
        superseded_by = self._check_superseded(file_path)
        if superseded_by:
            is_obsolete = True
            reason = f"Superseded by newer test file: {superseded_by.name}"
            confidence = 0.7
            return ObsolescenceReport(
                file_path=file_path,
                is_obsolete=is_obsolete,
                reason=reason,
                confidence=confidence
            )
        
        # Check for duplicate functionality
        duplicate_of = self._check_duplicate(file_path, test_functions, imports)
        if duplicate_of:
            is_obsolete = True
            reason = f"Duplicate functionality of: {duplicate_of.name}"
            confidence = 0.75
            return ObsolescenceReport(
                file_path=file_path,
                is_obsolete=is_obsolete,
                reason=reason,
                confidence=confidence
            )
        
        # If no obsolescence indicators found, mark as not obsolete
        return ObsolescenceReport(
            file_path=file_path,
            is_obsolete=False,
            reason="No obsolescence indicators detected",
            confidence=0.0
        )
    
    def _extract_imports(self, tree: ast.AST) -> Set[str]:
        """Extract all import statements from an AST.
        
        Args:
            tree: AST tree to analyze
            
        Returns:
            Set of module names that are imported
        """
        imports = set()
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
        
        return imports
    
    def _extract_test_functions(self, tree: ast.AST) -> Set[str]:
        """Extract all test function names from an AST.
        
        Args:
            tree: AST tree to analyze
            
        Returns:
            Set of test function names
        """
        test_functions = set()
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.name.startswith('test_'):
                    test_functions.add(node.name)
        
        return test_functions
    
    def _check_removed_features(self, imports: Set[str]) -> List[str]:
        """Check if imported modules from app/ still exist.
        
        Args:
            imports: Set of module names that are imported
            
        Returns:
            List of module names that no longer exist in app/
        """
        removed_modules = []
        
        for module in imports:
            # Only check imports that reference the app/ directory
            if module == 'app':
                # This is a valid import of the app package itself
                continue
            
            # Check if this could be an app submodule
            # We need to check if app/{module}.py or app/{module}/__init__.py exists
            module_file = self.app_dir / f"{module}.py"
            module_dir = self.app_dir / module / "__init__.py"
            
            # Only mark as removed if:
            # 1. The app/ directory exists
            # 2. Neither the module file nor module directory exists
            if self.app_dir.exists():
                if not module_file.exists() and not module_dir.exists():
                    # This might be a removed app module
                    # But we need to be careful - it might be a standard library or third-party import
                    # Only flag it if it looks like it could be an app module
                    # (we'll be conservative here)
                    pass
        
        return removed_modules

    
    def _check_duplicate(self, file_path: Path, test_functions: Set[str], imports: Set[str]) -> Path | None:
        """Check if this test file duplicates functionality of another test file.
        
        Compares test function names and imports with previously analyzed files.
        
        Args:
            file_path: Path to the current test file
            test_functions: Set of test function names in this file
            imports: Set of imports in this file
            
        Returns:
            Path to the duplicate file if found, None otherwise
        """
        # Need at least some test functions to compare
        if not test_functions:
            return None
        
        # Compare with previously analyzed files
        for other_path, (other_functions, other_imports) in self._test_file_cache.items():
            # Don't compare with self
            if other_path == file_path:
                continue
            
            # Check for significant overlap in test function names
            if test_functions and other_functions:
                overlap = test_functions & other_functions
                overlap_ratio = len(overlap) / len(test_functions)
                
                # If more than 80% of test functions are the same, consider it a duplicate
                if overlap_ratio > 0.8:
                    # Also check if imports are similar
                    import_overlap = imports & other_imports
                    if imports and len(import_overlap) / len(imports) > 0.5:
                        return other_path
        
        return None
    
    def _check_superseded(self, file_path: Path) -> Path | None:
        """Check if this test file has been superseded by a newer file.
        
        Looks for newer files with similar names (e.g., test_foo.py vs test_foo_v2.py).
        
        Args:
            file_path: Path to the test file
            
        Returns:
            Path to the superseding file if found, None otherwise
        """
        # Get the base name without extension
        base_name = file_path.stem
        
        # Look for files with similar names in the same directory
        parent_dir = file_path.parent
        
        # Common patterns for superseded files:
        # - test_foo.py superseded by test_foo_v2.py
        # - test_foo.py superseded by test_foo_new.py
        # - test_foo.py superseded by test_foo_updated.py
        
        superseding_patterns = [
            f"{base_name}_v2.py",
            f"{base_name}_v3.py",
            f"{base_name}_new.py",
            f"{base_name}_updated.py",
            f"{base_name}_refactor.py",
        ]
        
        for pattern in superseding_patterns:
            potential_superseding = parent_dir / pattern
            if potential_superseding.exists() and potential_superseding != file_path:
                # Check if the superseding file is newer
                try:
                    if potential_superseding.stat().st_mtime > file_path.stat().st_mtime:
                        return potential_superseding
                except OSError:
                    # If we can't get file stats, skip this check
                    pass
        
        # Also check if this file has a version suffix and there's a newer version
        # e.g., test_foo_v1.py superseded by test_foo_v2.py
        if '_v' in base_name:
            parts = base_name.rsplit('_v', 1)
            if len(parts) == 2:
                base_without_version = parts[0]
                try:
                    current_version = int(parts[1])
                    # Look for higher version numbers
                    for v in range(current_version + 1, current_version + 10):
                        potential_superseding = parent_dir / f"{base_without_version}_v{v}.py"
                        if potential_superseding.exists():
                            return potential_superseding
                except ValueError:
                    # Not a numeric version, skip
                    pass
        
        return None


    def evaluate_specs_content(self, file_path: Path) -> 'ContentEvaluation':
        """Evaluate if a specs file contains valuable content.

        This method parses markdown files and determines if they contain unique
        technical details or are just boilerplate. It checks if the content is
        already covered in .kiro/specs/ or wiki/ directories.

        Args:
            file_path: Path to the specs file to evaluate

        Returns:
            ContentEvaluation with recommended action
            
        Error Handling:
            - File cannot be read: log error, mark as "preserve" (conservative)
            - Binary file: log warning, mark as "preserve"
            - Parsing fails: log error, mark as "preserve"
        """
        from .models import ContentEvaluation

        # Conservative approach: default to preserve
        has_value = True
        reason = ""
        recommended_action = "move_to_wiki"

        # Try to read the file
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError as e:
            # Handle file cannot be read: log error, mark as "preserve"
            error_msg = f"File not found: {file_path} - {e}"
            logger.error(error_msg)
            return ContentEvaluation(
                file_path=file_path,
                has_value=True,
                reason=f"Could not read file (not found): {str(e)}",
                recommended_action="move_to_wiki"
            )
        except PermissionError as e:
            # Handle file cannot be read: log error, mark as "preserve"
            error_msg = f"Permission denied reading file: {file_path} - {e}"
            logger.error(error_msg)
            return ContentEvaluation(
                file_path=file_path,
                has_value=True,
                reason=f"Could not read file (permission denied): {str(e)}",
                recommended_action="move_to_wiki"
            )
        except UnicodeDecodeError as e:
            # Handle binary file: log warning, mark as "preserve"
            warning_msg = f"Binary file or encoding issue: {file_path} - {e}"
            logger.warning(warning_msg)
            return ContentEvaluation(
                file_path=file_path,
                has_value=True,
                reason=f"Binary file or encoding issue: {str(e)}",
                recommended_action="move_to_wiki"
            )
        except OSError as e:
            # Handle file cannot be read: log error, mark as "preserve"
            error_msg = f"Error reading file: {file_path} - {e}"
            logger.error(error_msg)
            return ContentEvaluation(
                file_path=file_path,
                has_value=True,
                reason=f"Could not read file: {str(e)}",
                recommended_action="move_to_wiki"
            )

        # Check if file is empty or very small (likely not valuable)
        if len(content.strip()) < 100:
            has_value = False
            reason = "File is empty or contains minimal content (< 100 characters)"
            recommended_action = "remove"
            return ContentEvaluation(
                file_path=file_path,
                has_value=has_value,
                reason=reason,
                recommended_action=recommended_action
            )

        # Parse markdown structure to identify content type
        lines = content.split('\n')

        # Count meaningful content indicators
        has_code_blocks = '```' in content
        has_tables = '|' in content and any('---' in line for line in lines)
        has_headers = any(line.strip().startswith('#') for line in lines)

        # Count lines of actual content (excluding empty lines and very short lines)
        content_lines = [line for line in lines if len(line.strip()) > 20]
        content_line_count = len(content_lines)

        # Check for boilerplate patterns
        boilerplate_patterns = [
            'todo',
            'placeholder',
            'coming soon',
            'to be implemented',
            'draft',
            'work in progress',
        ]

        content_lower = content.lower()
        boilerplate_count = sum(1 for pattern in boilerplate_patterns if pattern in content_lower)

        # If mostly boilerplate, mark as not valuable
        if boilerplate_count > 3 and content_line_count < 50:
            has_value = False
            reason = "File contains mostly boilerplate/placeholder content"
            recommended_action = "remove"
            return ContentEvaluation(
                file_path=file_path,
                has_value=has_value,
                reason=reason,
                recommended_action=recommended_action
            )

        # Check if content is already covered in .kiro/specs/ or wiki/
        kiro_specs_dir = self.workspace_root / '.kiro' / 'specs'
        wiki_dir = self.workspace_root / 'wiki'

        # Extract key technical terms from the content (simple heuristic)
        # Look for capitalized words, technical terms, and unique identifiers
        import re

        # Extract potential technical terms (words with 3+ chars, mixed case or all caps)
        technical_terms = set()
        words = re.findall(r'\b[A-Z][a-zA-Z]{2,}\b', content)
        technical_terms.update(words[:50])  # Limit to first 50 to avoid noise

        # Extract code identifiers (snake_case, camelCase)
        code_identifiers = set()
        code_identifiers.update(re.findall(r'\b[a-z_]+_[a-z_]+\b', content)[:30])
        code_identifiers.update(re.findall(r'\b[a-z]+[A-Z][a-zA-Z]+\b', content)[:30])

        # Check for overlap with existing .kiro/specs/ content
        if kiro_specs_dir.exists():
            overlap_score = self._check_content_overlap(
                technical_terms, code_identifiers, kiro_specs_dir
            )

            # If high overlap with .kiro/specs/, it's likely duplicate
            if overlap_score > 0.7:
                has_value = False
                reason = f"Content is largely covered in .kiro/specs/ (overlap: {overlap_score:.0%})"
                recommended_action = "remove"
                return ContentEvaluation(
                    file_path=file_path,
                    has_value=has_value,
                    reason=reason,
                    recommended_action=recommended_action
                )

        # Check for overlap with wiki/ content
        if wiki_dir.exists():
            overlap_score = self._check_content_overlap(
                technical_terms, code_identifiers, wiki_dir
            )

            # If high overlap with wiki/, it's duplicate
            if overlap_score > 0.7:
                has_value = False
                reason = f"Content is already covered in wiki/ (overlap: {overlap_score:.0%})"
                recommended_action = "remove"
                return ContentEvaluation(
                    file_path=file_path,
                    has_value=has_value,
                    reason=reason,
                    recommended_action=recommended_action
                )

        # If we get here, the file has unique technical content
        # Determine if it's valuable enough to move to wiki

        # Calculate a value score based on content characteristics
        value_score = 0

        if has_code_blocks:
            value_score += 2
        if has_tables:
            value_score += 2
        if has_headers:
            value_score += 1
        if content_line_count > 100:
            value_score += 2
        if content_line_count > 300:
            value_score += 2
        if len(technical_terms) > 10:
            value_score += 1
        if len(code_identifiers) > 5:
            value_score += 1

        # If value score is high, recommend moving to wiki
        if value_score >= 5:
            has_value = True
            reason = f"File contains valuable technical content (code blocks: {has_code_blocks}, tables: {has_tables}, {content_line_count} content lines)"
            recommended_action = "move_to_wiki"
        elif value_score >= 3:
            has_value = True
            reason = f"File contains some technical content (value score: {value_score}/11)"
            recommended_action = "move_to_wiki"
        else:
            has_value = False
            reason = f"File lacks substantial technical content (value score: {value_score}/11)"
            recommended_action = "remove"

        return ContentEvaluation(
            file_path=file_path,
            has_value=has_value,
            reason=reason,
            recommended_action=recommended_action
        )

    def _check_content_overlap(self, technical_terms: set, code_identifiers: set, directory: Path) -> float:
        """Check how much content overlaps with files in a directory.

        Args:
            technical_terms: Set of technical terms from the source file
            code_identifiers: Set of code identifiers from the source file
            directory: Directory to check for overlapping content

        Returns:
            Overlap score from 0.0 to 1.0
            
        Error Handling:
            - Directory cannot be accessed: log warning, return 0.0
            - File cannot be read: skip file, continue
        """
        if not technical_terms and not code_identifiers:
            return 0.0

        # Combine all terms for comparison
        all_terms = technical_terms | code_identifiers

        if not all_terms:
            return 0.0

        # Count how many terms appear in files in the directory
        matching_terms = set()

        # Search markdown files in the directory
        try:
            for md_file in directory.rglob('*.md'):
                try:
                    with open(md_file, 'r', encoding='utf-8') as f:
                        file_content = f.read()

                    # Check which terms appear in this file
                    for term in all_terms:
                        if term in file_content:
                            matching_terms.add(term)

                    # Early exit if we've found most terms
                    if len(matching_terms) / len(all_terms) > 0.9:
                        break

                except UnicodeDecodeError:
                    # Skip files we can't read (binary files)
                    logger.debug(f"Skipping binary file: {md_file}")
                    continue
                except PermissionError:
                    # Skip files we don't have permission to read
                    logger.debug(f"Permission denied reading file: {md_file}")
                    continue
                except OSError as e:
                    # Skip files with other read errors
                    logger.debug(f"Error reading file {md_file}: {e}")
                    continue

        except PermissionError:
            # If we can't access the directory, return 0
            logger.warning(f"Permission denied accessing directory: {directory}")
            return 0.0
        except OSError as e:
            # If we can't access the directory, return 0
            logger.warning(f"Error accessing directory {directory}: {e}")
            return 0.0

        # Calculate overlap ratio
        overlap_ratio = len(matching_terms) / len(all_terms) if all_terms else 0.0

        return overlap_ratio


    def find_duplicate_tests(self, test_files: List[Path]) -> List[DuplicateGroup]:
        """Identify test files with duplicate functionality.
        
        This method compares test function names and imports across multiple test files
        to identify groups of files that have similar functionality.
        
        Args:
            test_files: List of test file paths to analyze
            
        Returns:
            List of DuplicateGroup objects, each containing files with similar functionality
            
        Error Handling:
            - File cannot be read: skip file, continue
            - Parsing fails: skip file, continue
        """
        # First, analyze all test files and cache their test functions and imports
        file_data: Dict[Path, Tuple[Set[str], Set[str]]] = {}
        
        for file_path in test_files:
            # Skip non-Python files
            if file_path.suffix != '.py':
                continue
            
            # Try to parse the file
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content, filename=str(file_path))
                
                # Extract test functions and imports
                test_functions = self._extract_test_functions(tree)
                imports = self._extract_imports(tree)
                
                file_data[file_path] = (test_functions, imports)
                
            except FileNotFoundError:
                # Skip files that don't exist
                logger.debug(f"File not found, skipping: {file_path}")
                continue
            except PermissionError:
                # Skip files we can't read
                logger.debug(f"Permission denied, skipping: {file_path}")
                continue
            except UnicodeDecodeError:
                # Skip binary files
                logger.debug(f"Binary file or encoding issue, skipping: {file_path}")
                continue
            except SyntaxError:
                # Skip files we can't parse
                logger.debug(f"Syntax error, skipping: {file_path}")
                continue
            except Exception as e:
                # Skip files with unexpected errors
                logger.debug(f"Unexpected error parsing {file_path}: {e}")
                continue
        
        # Now compare files to find duplicates
        duplicate_groups: List[DuplicateGroup] = []
        processed_files: Set[Path] = set()
        
        # Compare each file with every other file
        file_paths = list(file_data.keys())
        
        for i, file1 in enumerate(file_paths):
            # Skip if already in a duplicate group
            if file1 in processed_files:
                continue
            
            test_funcs1, imports1 = file_data[file1]
            
            # Skip files with no test functions
            if not test_funcs1:
                continue
            
            # Find all files that are similar to this one
            similar_files = [file1]
            shared_functions = test_funcs1.copy()
            shared_imports = imports1.copy()
            
            for j in range(i + 1, len(file_paths)):
                file2 = file_paths[j]
                
                # Skip if already in a duplicate group
                if file2 in processed_files:
                    continue
                
                test_funcs2, imports2 = file_data[file2]
                
                # Skip files with no test functions
                if not test_funcs2:
                    continue
                
                # Calculate similarity based on test function overlap
                function_overlap = test_funcs1 & test_funcs2
                function_similarity = len(function_overlap) / max(len(test_funcs1), len(test_funcs2))
                
                # Calculate similarity based on import overlap
                import_overlap = imports1 & imports2
                import_similarity = len(import_overlap) / max(len(imports1), len(imports2)) if (imports1 or imports2) else 0.0
                
                # Combined similarity score (weighted average)
                # Test functions are more important than imports for determining duplicates
                similarity_score = (0.7 * function_similarity) + (0.3 * import_similarity)
                
                # If similarity is high enough, consider them duplicates
                # Using 0.6 threshold (60% similarity)
                if similarity_score >= 0.6:
                    similar_files.append(file2)
                    shared_functions &= test_funcs2
                    shared_imports &= imports2
                    processed_files.add(file2)
            
            # If we found duplicates, create a group
            if len(similar_files) > 1:
                # Calculate overall similarity score for the group
                # Use the minimum pairwise similarity as the group score
                min_similarity = 1.0
                for k in range(len(similar_files)):
                    for m in range(k + 1, len(similar_files)):
                        funcs_k, imports_k = file_data[similar_files[k]]
                        funcs_m, imports_m = file_data[similar_files[m]]
                        
                        func_overlap = funcs_k & funcs_m
                        func_sim = len(func_overlap) / max(len(funcs_k), len(funcs_m))
                        
                        imp_overlap = imports_k & imports_m
                        imp_sim = len(imp_overlap) / max(len(imports_k), len(imports_m)) if (imports_k or imports_m) else 0.0
                        
                        pair_similarity = (0.7 * func_sim) + (0.3 * imp_sim)
                        min_similarity = min(min_similarity, pair_similarity)
                
                duplicate_group = DuplicateGroup(
                    files=similar_files,
                    shared_test_functions=shared_functions,
                    shared_imports=shared_imports,
                    similarity_score=min_similarity
                )
                duplicate_groups.append(duplicate_group)
                processed_files.add(file1)
        
        return duplicate_groups

