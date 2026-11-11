// Findable Seller Dashboard: AG Grid Community configuration for real-time orders

document.addEventListener('DOMContentLoaded', () => {
    const gridDiv = document.querySelector('#ordersGrid');
    if (!gridDiv) return;

    const columnDefs = [
        { headerName: 'Order ID', field: 'order_id', width: 130, font: 'font-mono' },
        { headerName: 'PayPal Order ID', field: 'paypal_order_id', width: 160 },
        { 
            headerName: 'Channel', 
            field: 'channel', 
            width: 100,
            cellRenderer: (p) => {
                const isAgent = p.value === 'agent';
                return `<span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold ${isAgent ? 'bg-[#141414] text-[#a3e635] border border-[#262626]' : 'bg-[#141414] text-white border border-[#262626]'}">${p.value}</span>`;
            }
        },
        { headerName: 'Agent Name', field: 'agent', width: 130 },
        {
            headerName: 'Status',
            field: 'status',
            width: 130,
            cellRenderer: (p) => {
                const isCompleted = p.value === 'COMPLETED';
                const isRefunded = p.value === 'REFUNDED';
                const color = isCompleted ? 'bg-[#141414] text-[#a3e635] border border-[#262626]' : isRefunded ? 'bg-[#141414] text-red-400 border border-red-900' : 'bg-[#141414] text-white border border-[#262626]';
                return `<span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold ${color}">${p.value}</span>`;
            }
        },
        { headerName: 'Total', field: 'total', width: 90, font: 'font-bold' },
        { headerName: 'Capture ID', field: 'capture_id', width: 150 },
        { 
            headerName: 'Passport Bundle Hash', 
            field: 'passport_hash', 
            flex: 1,
            cellRenderer: (p) => `<span class="font-mono text-[10px] text-[#71717a]">${p.value}</span>`
        }
    ];

    const defaultData = [
        { order_id: 'ord_7a9f2b1c', paypal_order_id: '9X482018AL391824P', channel: 'agent', agent: 'claude-desktop', status: 'COMPLETED', total: '$28.00', capture_id: 'CAP-9X124819', passport_hash: '7f83b1657ff1...' },
        { order_id: 'ord_3c810d4e', paypal_order_id: '6Y194829CL491023Q', channel: 'agent', agent: 'findable-web', status: 'COMPLETED', total: '$28.00', capture_id: 'CAP-3K891204', passport_hash: '9e10284ab910...' }
    ];

    const rowData = (window.ordersData && window.ordersData.length > 0) ? window.ordersData : defaultData;

    const gridOptions = {
        columnDefs: columnDefs,
        rowData: rowData,
        rowHeight: 40,
        headerHeight: 38,
        defaultColDef: {
            sortable: true,
            filter: true,
            resizable: true,
        }
    };

    agGrid.createGrid(gridDiv, gridOptions);
});

