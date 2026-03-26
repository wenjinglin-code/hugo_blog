// GitHub 风格目录折叠功能 - 每级目录都可折叠
document.addEventListener('DOMContentLoaded', function() {
  // 兼容 class="toc" 和 id="TableOfContents" 两种选择器
  const toc = document.querySelector('.toc') || document.getElementById('TableOfContents');
  if (!toc) return;
  
  // 防止重复执行
  if (toc.dataset.processed === 'true') return;
  toc.dataset.processed = 'true';

  const tocUl = toc.querySelector('ul');
  if (!tocUl) return;

  // 递归处理所有级别的目录
  function processTocList(ul) {
    const items = ul.querySelectorAll(':scope > li');
    
    items.forEach(function(li) {
      // 检查是否有子目录 (ul 元素)
      const subUl = li.querySelector(':scope > ul');
      
      if (subUl) {
        // 跳过已经有 details 包装的元素
        if (li.querySelector('.toc-details')) return;
        
        // 获取当前项的第一个文本节点（在清空之前）
        let itemText = '';
        // 首先检查是否有链接文本
        const link = li.querySelector(':scope > a');
        if (link) {
          itemText = link.textContent.trim();
        } else {
          // 如果没有链接，获取文本节点
          for (let node of li.childNodes) {
            if (node.nodeType === Node.TEXT_NODE && node.textContent.trim()) {
              itemText = node.textContent.trim();
              break;
            }
          }
        }
        
        // 创建 details 元素
        const details = document.createElement('details');
        details.className = 'toc-details';
        details.open = true; // 默认展开
        
        // 创建 summary 元素用于点击折叠
        const summary = document.createElement('summary');
        summary.textContent = itemText;
        summary.title = '点击折叠/展开';
        
        // 获取子目录内容
        const newUl = document.createElement('ul');
        newUl.innerHTML = subUl.innerHTML;
        
        // 递归处理子目录
        processTocList(newUl);
        
        // 组装 details
        details.appendChild(summary);
        details.appendChild(newUl);
        
        // 替换原来的内容，保留链接
        li.innerHTML = '';
        if (link) {
          // 将链接添加到summary中
          const linkSpan = document.createElement('span');
          linkSpan.className = 'toc-link';
          linkSpan.textContent = itemText;
          summary.textContent = '';
          summary.appendChild(linkSpan);
        }
        li.appendChild(details);
      }
    });
  }

  // 从最外层开始处理
  processTocList(tocUl);
});
