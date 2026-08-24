"""策略结果构造模块。

每个策略文件包含一个或多个策略判定函数，统一返回
{code, name, passed, score, signal_strength, reasons, details} 七字段字典，
确保组合引擎可统一调用、报告层可统一消费。
"""


def clean_klines(klines: list) -> list:
    """剔除关键字段（open/close/high/low/volume）为 None 的无效 K 线。

    数据源字段缺失时如实剔除，避免后续判定对 None 做运算崩溃；
    正常数据（字段完整）不受影响。
    """
    return [
        k for k in klines
        if all(k.get(f) is not None for f in ("open", "close", "high", "low", "volume"))
    ]


def make_result(code: str, name: str, passed: bool, score: float,
                reasons: list = None, details: dict = None,
                signal_strength: str = None) -> dict:
    """快捷构造策略判定结果字典。

    Args:
        code: 策略编号（与注册表键一致，如 'S01'）
        name: 策略名称
        passed: 是否通过
        score: 归一化得分
        reasons: 判定理由列表
        details: 详细判定数据
        signal_strength: 信号强度 '强'/'中'/'弱'；None 表示未达到任何信号级别

    Returns:
        dict: {code, name, passed, score, signal_strength, reasons, details}

    契约：
    - 失败策略（passed=False 且 score<=0）signal_strength 恒为 None；
    - 仅当 score>0 时才按分值推导 '弱'/'中'/'强'，避免失败策略被误标为弱信号。
    """
    if signal_strength is None and score > 0:
        signal_strength = "强" if score >= 0.7 else ("中" if score >= 0.4 else "弱")
    return {
        "code": code,
        "name": name,
        "passed": passed,
        "score": round(score, 4),
        "signal_strength": signal_strength,
        "reasons": reasons or [],
        "details": details or {},
    }
