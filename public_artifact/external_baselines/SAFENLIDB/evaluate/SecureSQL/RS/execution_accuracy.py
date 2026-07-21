import os
import sqlite3
import time
import logging
import pandas as pd
from typing import Tuple, Any, List
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FutureTimeout

# Logging configuration
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(message)s')

# Global process pool: based on the CPU count or a custom size
POOL = ProcessPoolExecutor(max_workers=os.cpu_count() or 4)

# Timeout settings
MAX_EXECUTION_MS = 4000
TIMEOUT_S = MAX_EXECUTION_MS / 1000

def _worker(db_url: str, query: str) -> Tuple[str, Any, int]:
    """Execute SQL in a subprocess and return (flag, DataFrame|None|Exception, ms)"""
    start = time.time()
    conn = None
    cur = None
    try:
        if db_url.startswith("sqlite:///"):
            db_url = db_url[10:]
        conn = sqlite3.connect(db_url)
        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchall()
        cols = [c[0] for c in cur.description] if cur.description else []
        df = pd.DataFrame(rows, columns=cols)
        elapsed = int((time.time() - start) * 1000)
        if elapsed > MAX_EXECUTION_MS:
            return "timeout", None, elapsed
        return "result", df, elapsed
    except Exception as e:
        return "exception", e, 0
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def exec_on_db_proc(db_url: str, query: str, timeout_s: float = TIMEOUT_S) -> Tuple[str, Any, int]:
    """
    Submit a task using the global process pool and wait for timeout_s seconds:
      - Normal execution: returns the output from _worker
      - Timeout: cancels the task and returns ("timeout", None, 0)
      - Exception: captures and returns ("exception", Exception, 0)
    """
    future = POOL.submit(_worker, db_url, query)
    try:
        flag, data, ms = future.result(timeout=timeout_s)
        logging.debug(f"exec_on_db_proc done: flag={flag}, time={ms}ms")
        return flag, data, ms
    except FutureTimeout:
        logging.warning(f"Query future timeout after {timeout_s}s, cancelling task")
        future.cancel()
        return "timeout", None, 0
    except Exception as e:
        logging.error(f"exec_on_db_proc unexpected error: {e}", exc_info=True)
        return "exception", e, 0

def _compute_metric(prediction: str, reference: str, db_url: str) -> dict:
    """
    Compare a single SQL prediction vs reference by execution:
      - Skip on timeout or exception (raises TimeoutError),
      - Otherwise, returns {"results": 1 or 0}.
    """
    logging.debug(f"Evaluating SQL on {db_url}\nREF: {reference}\nPRED: {prediction}")

    # 1. Execute reference query
    ref_flag, ref_df, ref_ms = exec_on_db_proc(db_url, reference)
    logging.debug(f"Reference -> flag={ref_flag}, time={ref_ms}ms")
    if ref_flag == "timeout":
        raise TimeoutError(f"Reference timeout ({ref_ms}ms)")
    if ref_flag == "exception" or not isinstance(ref_df, pd.DataFrame):
        logging.warning("Reference exception -> using empty DataFrame")
        ref_df = pd.DataFrame()

    # 2. Execute prediction query
    pred_flag, pred_df, pred_ms = exec_on_db_proc(db_url, prediction)
    logging.debug(f"Prediction -> flag={pred_flag}, time={pred_ms}ms")
    if pred_flag == "timeout":
        raise TimeoutError(f"Prediction timeout ({pred_ms}ms)")
    if pred_flag == "exception" or not isinstance(pred_df, pd.DataFrame):
        logging.warning("Prediction exception -> using empty DataFrame")
        pred_df = pd.DataFrame()

    # 3. Normalize for comparison
    #   - sort columns, cast to str
    pred_norm = pred_df.sort_index(axis=1).astype(str)
    ref_norm  = ref_df.sort_index(axis=1).astype(str)
    logging.debug(f"Normalized shapes -> pred: {pred_norm.shape}, ref: {ref_norm.shape}")

    # 4. If shapes don't match, return result 0
    if len(pred_norm) != len(ref_norm) or len(pred_norm.columns) != len(ref_norm.columns):
        logging.info("Shape mismatch -> incorrect")
        return {"results": 0}

    # 5. Align column names (if names differ, match by content)
    common_pred: List[str] = []
    common_ref:  List[str] = []
    for pc in pred_norm.columns:
        if pc in ref_norm.columns and pc not in common_ref:
            common_pred.append(pc)
            common_ref.append(pc)
        else:
            for rc in ref_norm.columns:
              try:
                if rc not in common_ref and pred_norm[pc].sort_values(ignore_index=True).equals(
                        ref_norm[rc].sort_values(ignore_index=True)):
                    common_pred.append(pc)
                    common_ref.append(rc)
                    break
              except:
                  continue
    logging.debug(f"Column mapping -> {list(zip(common_pred, common_ref))}")
    if len(common_pred) != len(pred_norm.columns):
        logging.info("Failed to align all columns -> incorrect")
        return {"results": 0}

    # 6. Sort rows and compare
    pred_aligned = pred_norm[common_pred].sort_values(by=common_pred, ignore_index=True)
    ref_aligned  = ref_norm[common_ref].sort_values(by=common_ref, ignore_index=True)
    ref_aligned.columns = pred_aligned.columns

    correct = pred_aligned.equals(ref_aligned)
    logging.debug(f"Row-by-row comparison -> {correct}")
    return {"results": int(correct)}

def compute_evaluation_accuracy(
        predictions: List[str],
        references:  List[str],
        db_urls:     List[str]
) -> dict:
    """
    Perform an overall execution accuracy evaluation on multiple SQL queries:
      - Skip entries with timeouts or exceptions,
      - Return {"results": [...], "skipped": n, "execution_accuracy": float}
    """
    results: List[int] = []
    skipped = 0

    for idx, (pred, ref, db) in enumerate(zip(predictions, references, db_urls)):
        logging.debug(f"Index {idx}, DB={db}")
        if not os.path.exists(db):
            logging.warning(f"Database not found: {db}")
            skipped += 1
            continue

        try:
            metric = _compute_metric(pred, ref, db)
        except TimeoutError as e:
            logging.warning(f"Skipping idx {idx} due to timeout: {e}")
            skipped += 1
            continue

        results.append(metric.get("results", 0))
        logging.debug(f"Metric idx {idx}: {metric}")

    total = len(results)
    accuracy = sum(results) / total if total > 0 else 0.0
    logging.info(f"Evaluation done: non-skipped={total}, skipped={skipped}, accuracy={accuracy:.4f}")
    return {"results": results, "skipped": skipped, "execution_accuracy": accuracy}
