async function uploadScreenshot() {
    const input = document.getElementById('screenshotInput');
    const model = document.getElementById('model').value;
    const file = input.files[0];
    const status = document.getElementById('status');

    if (!file) {
        status.textContent = '请先选择一张图片！';
        return;
    }

    // 显示预览
    const preview = document.getElementById('preview');
    const img = document.createElement('img');
    img.src = URL.createObjectURL(file);
    preview.innerHTML = '';
    preview.appendChild(img);

    // 更新状态
    status.textContent = '正在处理...';

    // 上传图片
    const formData = new FormData();
    formData.append('file', file);
    formData.append('model', model);

    try {
        const response = await fetch('/api/recognize', {
            method: 'POST',
            body: formData
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const result = await response.json();

        // 显示 LaTeX
        const latexCode = document.getElementById('latexCode');
        latexCode.textContent = result.latex || '未识别到公式';

        // 渲染公式
        const formula = document.getElementById('formula');
        if (result.latex) {
            katex.render(result.latex, formula, { throwOnError: false });
        } else {
            formula.textContent = '无公式可渲染';
        }

        status.textContent = '处理完成！';
    } catch (error) {
        console.error('上传失败:', error);
        status.textContent = `错误：${error.message}`;
    }
}

function copyLatex() {
    const latexCode = document.getElementById('latexCode').textContent;
    navigator.clipboard.writeText(latexCode).then(() => {
        alert('LaTeX 代码已复制！');
    }).catch(err => {
        alert('复制失败：' + err);
    });
} 
