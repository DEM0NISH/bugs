window.BUGTRACE_PREVIEW_RESULTS = {
  sample_size: 6,
  passed: 6,
  cases: [
    { case_id: "BT-01", title: "Multi-line quote ignores supplier discount", actual: "defect_indicated", pass: true },
    { case_id: "BT-02", title: "GST rounds each line before summing", actual: "defect_indicated", pass: true },
    { case_id: "BT-03", title: "Idempotent retry creates another quote", actual: "defect_indicated", pass: true },
    { case_id: "BT-04", title: "Confirmed cancellation leaves credit reserved", actual: "defect_indicated", pass: true },
    { case_id: "NC-01", title: "No discount is due for this supplier", actual: "no_defect_found", pass: true },
    { case_id: "NC-02", title: "Request cannot be located", actual: "insufficient_evidence", pass: true },
  ],
};
