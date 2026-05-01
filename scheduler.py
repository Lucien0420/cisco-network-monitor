from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import traceback
from typing import List, Dict, Any, Callable, Optional
from logger_config import setup_logger

scheduler_logger = setup_logger('scheduler')

class DeviceScheduler:
    def __init__(self, max_workers=10):
        self.max_workers = max_workers
        self.executor = None

    def __enter__(self):
        """Support with statement, auto-start executor."""
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Shutdown executor on exit."""
        if self.executor:
            self.executor.shutdown(wait=True)

    def _format_target(self, target):
        """Format target for display (dict: show ip or host)."""
        if isinstance(target, dict):
            return target.get('ip') or target.get('host') or str(target)
        return str(target)
    def run_tasks(self, task_func: Callable, target_list: List[Any], 
                  timeout: Optional[float] = None, 
                  show_progress: bool = True,
                  warn_infinite_tasks: bool = True) -> Dict[str, Any]:
        """
        Run tasks with exception handling and progress tracking.

        Args:
            task_func: Task function to run
            target_list: List of targets
            timeout: Per-task timeout (seconds), None = no timeout
            show_progress: Show progress
            warn_infinite_tasks: Warn if tasks may run forever

        Returns:
            Dict with success, failed, stats

        Warning:
            If tasks may run forever (e.g. no duration/max_iterations) and timeout is None,
            this will block indefinitely. Set timeout or task stop conditions.
        """
        if not self.executor:
            raise RuntimeError("Executor not initialized. Use with statement.")
        
        if not target_list:
            return {
                'success': [],
                'failed': [],
                'stats': {'total': 0, 'success_count': 0, 'failed_count': 0}
            }
        
        # Warn if tasks may run forever
        if warn_infinite_tasks and timeout is None:
            for target in target_list:
                if isinstance(target, dict):
                    has_duration = target.get('monitor_duration') is not None
                    has_max_iter = target.get('monitor_max_iterations') is not None
                    if not has_duration and not has_max_iter:
                        scheduler_logger.warning(
                            f"Task {self._format_target(target)} may run forever! "
                            "Set timeout or monitor_duration/monitor_max_iterations."
                        )
        
        total = len(target_list)
        future_to_target = {
            self.executor.submit(task_func, target): target
            for target in target_list
        }
        
        success_results = []
        failed_results = []
        completed = 0
        for future in as_completed(future_to_target):
            target = future_to_target[future]
            target_display = self._format_target(target)
            completed += 1
            
            try:
                if timeout:
                    data = future.result(timeout=timeout)
                else:
                    data = future.result()
                
                success_results.append({
                    'target': target,
                    'data': data
                })
                
                scheduler_logger.info(f"[{completed}/{total}] {target_display} completed")
                if show_progress:
                    print(f"[SUCCESS] [{completed}/{total}] {target_display} completed")
                    
            except TimeoutError:
                error_msg = f"Task timeout ({timeout}s)"
                failed_results.append({
                    'target': target,
                    'error': error_msg,
                    'traceback': None
                })
                scheduler_logger.warning(f"[{completed}/{total}] {target_display} {error_msg}")
                if show_progress:
                    print(f"[TIMEOUT] [{completed}/{total}] {target_display} {error_msg}")
                    
            except Exception as e:
                error_traceback = traceback.format_exc()
                failed_results.append({
                    'target': target,
                    'error': str(e),
                    'traceback': error_traceback
                })
                scheduler_logger.error(f"[{completed}/{total}] {target_display} failed: {e}", exc_info=True)
                if show_progress:
                    print(f"[ERROR] [{completed}/{total}] {target_display} failed: {e}")
        
        stats = {
            'total': total,
            'success_count': len(success_results),
            'failed_count': len(failed_results)
        }
        
        scheduler_logger.info(f"Tasks done - total: {total} | success: {stats['success_count']} | failed: {stats['failed_count']}")
        if show_progress:
            print(f"\n[Stats] total: {total} | success: {stats['success_count']} | failed: {stats['failed_count']}")
        
        return {
            'success': success_results,
            'failed': failed_results,
            'stats': stats
        }