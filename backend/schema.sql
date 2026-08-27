-- ============================================================
-- 微信商城数据统计后台 · MySQL 建表脚本
-- 字符集统一 utf8mb4，支持 emoji 与中文
-- 用法：mysql -u<user> -p <dbname> < schema.sql
-- ============================================================
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `products` (
  `id`                INT AUTO_INCREMENT PRIMARY KEY,
  `name`              VARCHAR(255) NOT NULL COMMENT '商品名称',
  `sku`               VARCHAR(128) NOT NULL COMMENT 'SKU 编号',
  `default_cost_price` DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '默认成本价',
  `category_l1`       VARCHAR(128) NOT NULL DEFAULT '' COMMENT '大分类',
  `category_l2`       VARCHAR(128) NOT NULL DEFAULT '' COMMENT '中分类',
  `category_l3`       VARCHAR(128) NOT NULL DEFAULT '' COMMENT '小分类',
  `created_at`        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_sku` (`sku`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品表';

CREATE TABLE IF NOT EXISTS `campaigns` (
  `id`         INT AUTO_INCREMENT PRIMARY KEY,
  `name`       VARCHAR(255) NOT NULL COMMENT '活动名称',
  `start_date` DATETIME NOT NULL COMMENT '开始时间',
  `end_date`   DATETIME NOT NULL COMMENT '结束时间',
  `status`     TINYINT NOT NULL DEFAULT 1 COMMENT '1进行中 0已结束 -1已隐藏',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='活动主表';

CREATE TABLE IF NOT EXISTS `campaign_items` (
  `id`               INT AUTO_INCREMENT PRIMARY KEY,
  `campaign_id`      INT NOT NULL,
  `product_id`       INT NOT NULL,
  `activity_price`   DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '该期活动售价',
  `cost_price`       DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '该期成本',
  `is_bundle`        TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否捆绑特价',
  `bundle_quantity`  INT NOT NULL DEFAULT 1 COMMENT '捆绑数量',
  `total_sold_count` INT NOT NULL DEFAULT 0 COMMENT '累计销量（可定时更新）',
  FOREIGN KEY (`campaign_id`) REFERENCES `campaigns`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`product_id`)  REFERENCES `products`(`id`)  ON DELETE CASCADE,
  KEY `idx_campaign` (`campaign_id`),
  KEY `idx_product` (`product_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='活动商品关联表';

CREATE TABLE IF NOT EXISTS `orders_sync` (
  `id`               INT AUTO_INCREMENT PRIMARY KEY,
  `order_id`         VARCHAR(64) NOT NULL COMMENT '微信订单号',
  `product_id`       INT DEFAULT NULL COMMENT '匹配到的商品 id',
  `quantity`         INT NOT NULL DEFAULT 0 COMMENT '数量',
  `pay_price`        DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '实付金额',
  `order_time`       DATETIME NOT NULL COMMENT '下单时间',
  `sync_date`        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `campaign_item_id` INT DEFAULT NULL COMMENT '关联的活动商品行',
  KEY `idx_order` (`order_id`),
  KEY `idx_order_time` (`order_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单同步原始表';

CREATE TABLE IF NOT EXISTS `cost_change_logs` (
  `id`          INT AUTO_INCREMENT PRIMARY KEY,
  `product_id`  INT NOT NULL,
  `old_cost`    DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '旧成本',
  `new_cost`    DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '新成本',
  `operator`    VARCHAR(64) NOT NULL DEFAULT 'admin' COMMENT '操作人',
  `change_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (`product_id`) REFERENCES `products`(`id`) ON DELETE CASCADE,
  KEY `idx_product` (`product_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='成本修改日志';
