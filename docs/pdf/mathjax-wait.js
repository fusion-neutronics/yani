// Holds Paged.js back until MathJax has typeset the page. mkdocs-exporter calls
// `MkDocsExporter.render` before Paged.js splits the page into A4 sheets, so
// the breaks are placed using the typeset equations rather than the raw TeX.
window.MkDocsExporter = {
  render: async () => {
    while (!(window.MathJax && MathJax.startup && MathJax.startup.promise)) {
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
    await MathJax.startup.promise;
    await MathJax.typesetPromise();
  },
};
